"""
Pruebas de integración: la API real contra SQL Server real (stack de docker compose).

Cada resultado de la API se compara con una consulta directa a la base de datos,
así se verifica toda la cadena: CSV -> ETL -> SQL Server -> vistas -> API.

    docker compose up -d --build
    python -m pytest tests/integration -v

Si la API no responde, las pruebas se omiten (no fallan): el resto de la suite
se puede ejecutar sin Docker.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

import pytest
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("API_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}
NIVEL = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _api_disponible() -> bool:
    """True solo si responde ESTA API: otro programa podría estar usando el mismo puerto."""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as r:
            return r.status == 200 and json.loads(r.read()).get("estado") == "ok"
    except (urllib.error.URLError, OSError, ValueError):
        return False


pytestmark = pytest.mark.skipif(not _api_disponible(), reason=f"la API no responde en {BASE_URL}")


def get(path: str, params: dict | None = None, headers: dict | None = None, method: str = "GET"):
    query = "?" + urllib.parse.urlencode(params, doseq=True) if params else ""
    request = urllib.request.Request(BASE_URL + path + query, method=method,
                                     headers=HEADERS if headers is None else headers)
    try:
        with urllib.request.urlopen(request) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def sql(query: str) -> list[list[str]]:
    """Consulta directa a SQL Server con sqlcmd dentro del contenedor (como administrador)."""
    resultado = subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "/opt/mssql-tools18/bin/sqlcmd", "-C", "-S", "localhost",
         "-U", "sa", "-P", DB_PASSWORD, "-d", "alarmas", "-h", "-1", "-W", "-s", "|",
         "-Q", "SET NOCOUNT ON; " + query],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return [linea.split("|") for linea in resultado.stdout.strip().splitlines()]


def sql_count(where: str = "") -> int:
    return int(sql(f"SELECT COUNT(*) FROM v_evento_alarma {where}")[0][0])


def es_error(body: dict, codigo: str) -> bool:
    return set(body) == {"error"} and body["error"]["codigo"] == codigo


# --------------------------------------------------------------------------- #
# GET /api/v1/alarmas
# --------------------------------------------------------------------------- #


def test_sin_filtros_el_total_coincide_con_la_bd():
    status, body = get("/api/v1/alarmas")
    assert status == 200
    assert body["total"] == sql_count()
    assert body["pages"] == -(-body["total"] // 50)


def test_paginas_consecutivas_no_repiten_eventos():
    _, pagina1 = get("/api/v1/alarmas", {"page": 1, "size": 50})
    _, pagina2 = get("/api/v1/alarmas", {"page": 2, "size": 50})
    assert not {i["id"] for i in pagina1["items"]} & {i["id"] for i in pagina2["items"]}


def test_orden_descendente_y_fechas_en_utc():
    _, body = get("/api/v1/alarmas", {"size": 100})
    fechas = [i["timestamp_utc"] for i in body["items"]]
    assert fechas == sorted(fechas, reverse=True)
    assert all(f.endswith("Z") for f in fechas)


@pytest.mark.parametrize("params, where", [
    ({"desde": "2026-07-01", "hasta": "2026-07-02"},
     "WHERE timestamp_utc >= '2026-07-01' AND timestamp_utc < '2026-07-02'"),
    ({"desde": "2026-07-01T19:00:00-05:00", "hasta": "2026-07-02T19:00:00-05:00"},   # hora local de planta
     "WHERE timestamp_utc >= '2026-07-02' AND timestamp_utc < '2026-07-03'"),
    ({"criticidad_min": "HIGH"}, "WHERE criticidad_nivel >= 3"),
    ({"criticidad": ["LOW", "CRITICAL"]}, "WHERE criticidad IN ('LOW', 'CRITICAL')"),
    ({"tag": "PT-101"}, "WHERE tag = 'PT-101'"),
    ({"tag": "pt_101"}, "WHERE tag = 'PT-101'"),                                     # variante sucia
    ({"estado": "ACK"}, "WHERE estado = 'ACK'"),
    ({"tag": "PT-101", "criticidad_min": "HIGH", "estado": "ACTIVE", "desde": "2026-07-01", "hasta": "2026-07-08"},
     "WHERE tag = 'PT-101' AND criticidad_nivel >= 3 AND estado = 'ACTIVE' "
     "AND timestamp_utc >= '2026-07-01' AND timestamp_utc < '2026-07-08'"),
])
def test_filtros_coinciden_con_la_bd(params, where):
    status, body = get("/api/v1/alarmas", params)
    assert status == 200
    assert body["total"] == sql_count(where)


def test_filtros_se_respetan_en_cada_evento():
    _, body = get("/api/v1/alarmas", {"tag": "PT-101", "criticidad_min": "HIGH", "size": 500})
    assert all(i["tag"] == "PT-101" and NIVEL[i["criticidad"]] >= 3 for i in body["items"])


def test_evento_trae_unidad_y_limite_del_catalogo():
    _, body = get("/api/v1/alarmas", {"tag": "PT-101", "size": 1})
    evento = body["items"][0]
    assert (evento["unidad"], evento["limite"]) == ("bar", 8.5)


@pytest.mark.parametrize("params", [
    {"desde": "ayer"}, {"desde": "2026-07-08", "hasta": "2026-07-01"}, {"criticidad": "SUPER"},
    {"criticidad": "HIGH", "criticidad_min": "LOW"}, {"tag": "PT-101' OR '1'='1"}, {"size": 501},
    {"criticiad": "HIGH"},
])
def test_parametros_invalidos_son_422(params):
    status, body = get("/api/v1/alarmas", params)
    assert status == 422 and es_error(body, "VALIDACION")


def test_tag_inexistente_es_404():
    status, body = get("/api/v1/alarmas", {"tag": "XX-999"})
    assert status == 404 and es_error(body, "NO_ENCONTRADO")


def test_sin_api_key_es_401():
    if not API_KEY:
        pytest.skip("la API no tiene API_KEY configurada")
    status, body = get("/api/v1/alarmas", headers={})
    assert status == 401 and es_error(body, "NO_AUTORIZADO")


# --------------------------------------------------------------------------- #
# GET /api/v1/alarmas/{id}
# --------------------------------------------------------------------------- #


def test_detalle_coincide_con_la_bd():
    id_evento, origen, tag = sql("SELECT TOP 1 id, id_evento_origen, tag FROM v_evento_alarma ORDER BY NEWID()")[0]
    status, body = get(f"/api/v1/alarmas/{id_evento}")
    assert status == 200
    assert (body["id_evento_origen"], body["tag"]) == (int(origen), tag)


def test_detalle_inexistente_es_404():
    assert get("/api/v1/alarmas/999999999")[0] == 404


# --------------------------------------------------------------------------- #
# Métricas y catálogo
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("params, where", [
    ({}, "WHERE estado = 'ACTIVE'"),
    ({"contar": "eventos"}, ""),
    ({"criticidad_min": "CRITICAL", "desde": "2026-08-01", "hasta": "2026-09-01"},
     "WHERE estado = 'ACTIVE' AND criticidad_nivel >= 4 AND timestamp_utc >= '2026-08-01' "
     "AND timestamp_utc < '2026-09-01'"),
])
def test_top_tags_coincide_con_la_bd(params, where):
    esperado = sql(f"SELECT TOP 5 tag, COUNT(*) FROM v_evento_alarma {where} GROUP BY tag ORDER BY COUNT(*) DESC, tag")
    status, body = get("/api/v1/metricas/top-tags", {**params, "limit": 5})
    assert status == 200
    assert [(i["tag"], i["total"]) for i in body["items"]] == [(t, int(n)) for t, n in esperado]


def test_por_criticidad_coincide_con_la_bd():
    esperado = dict(sql("SELECT criticidad, COUNT(*) FROM v_evento_alarma WHERE estado = 'ACTIVE' GROUP BY criticidad"))
    _, body = get("/api/v1/metricas/por-criticidad")
    assert {i["criticidad"]: i["total"] for i in body["items"]} == {k: int(v) for k, v in esperado.items()}


def test_catalogo_coincide_con_la_bd():
    esperado = sql("SELECT tag, tipo_alarma, limite, criticidad FROM v_catalogo")
    _, body = get("/api/v1/tags")
    api = {(t["tag"], a["tipo_alarma"], a["limite"], a["criticidad"]) for t in body for a in t["alarmas"]}
    assert api == {(t, tipo, float(limite), c) for t, tipo, limite, c in esperado}


# --------------------------------------------------------------------------- #
# Seguridad: el usuario de la API es de solo lectura
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("sentencia", ["SELECT TOP 1 * FROM dbo.evento_alarma", "DELETE FROM dbo.evento_alarma"])
def test_usuario_de_la_api_no_puede_leer_tablas_ni_borrar(sentencia):
    usuario = os.environ.get("DB_API_USER", "api_lectura")
    resultado = subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "/opt/mssql-tools18/bin/sqlcmd", "-C", "-S", "localhost",
         "-U", usuario, "-P", os.environ.get("DB_API_PASSWORD", ""), "-d", "alarmas", "-Q", sentencia],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert "permission was denied" in resultado.stdout + resultado.stderr
