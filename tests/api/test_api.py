"""
Tests de la API sin base de datos: el repositorio real se reemplaza por uno falso
mediante dependency_overrides. Se prueban validaciones, códigos de estado y el
formato de las respuestas; el SQL se prueba contra SQL Server en la verificación.
"""

from datetime import datetime
from decimal import Decimal

import pyodbc
import pytest
from fastapi.testclient import TestClient

from api.config import ApiSettings, get_api_settings
from api.db import get_repository
from api.main import app
from api.schemas import NIVEL, Criticidad

EVENTO = {
    "id": 3, "id_evento_origen": 3, "timestamp_utc": datetime(2026, 7, 2, 0, 11, 11, 35_000),
    "tag": "PT-101", "descripcion": "Presión descarga bomba P-101", "area": "Bombeo",
    "tipo_alarma": "HI", "criticidad": "HIGH", "estado": "ACTIVE", "valor": 8.552,
    "calidad_valor": "GOOD", "unidad": "bar", "limite": Decimal("8.5000"),
    "desviacion_limite": Decimal("0.0520"),
}


class FakeRepository:
    def __init__(self):
        self.ultimo_filtro = None

    def listar(self, f):
        self.ultimo_filtro = f
        return [EVENTO], 101

    def obtener(self, id_evento):
        return EVENTO if id_evento == 3 else None

    def existe_tag(self, codigo):
        return codigo == "PT-101"

    def top_tags(self, f):
        self.ultimo_filtro = f
        return [{"tag": "PT-101", "descripcion": "Presión descarga bomba P-101", "area": "Bombeo", "total": 1786}]

    def por_criticidad(self, f):
        return [{"criticidad": c, "nivel": NIVEL[c], "total": 10} for c in Criticidad]

    def tags(self):
        return []

    def ping(self):
        pass


@pytest.fixture
def repo():
    return FakeRepository()


@pytest.fixture
def client(repo):
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_api_settings] = lambda: ApiSettings(api_key=None, cors_origins=[])
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _error(response):
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"codigo", "mensaje", "detalle"}
    return body["error"]


# --------------------------------------------------------------------------- #
# Consultas exitosas
# --------------------------------------------------------------------------- #


def test_listar_alarmas_sin_filtros(client):
    response = client.get("/api/v1/alarmas")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 101 and body["page"] == 1 and body["size"] == 50 and body["pages"] == 3
    item = body["items"][0]
    assert item["timestamp_utc"] == "2026-07-02T00:11:11.035000Z"     # UTC explícito
    assert item["limite"] == 8.5 and item["unidad"] == "bar"


def test_filtros_se_normalizan(client, repo):
    response = client.get("/api/v1/alarmas", params={
        "tag": "pt_101", "desde": "2026-07-01T19:00:00-05:00", "criticidad": ["HIGH", "CRITICAL"],
    })
    assert response.status_code == 200
    f = repo.ultimo_filtro
    assert f.tag == "PT-101"                                      # misma regla que el ETL
    assert f.desde.isoformat() == "2026-07-02T00:00:00+00:00"     # convertido a UTC
    assert f.criticidad == [Criticidad.HIGH, Criticidad.CRITICAL]


def test_fecha_sin_zona_se_interpreta_como_utc(client, repo):
    client.get("/api/v1/alarmas", params={"desde": "2026-07-01"})
    assert repo.ultimo_filtro.desde.isoformat() == "2026-07-01T00:00:00+00:00"


def test_obtener_alarma(client):
    assert client.get("/api/v1/alarmas/3").json()["id"] == 3


def test_top_tags_cuenta_alarmas_por_defecto(client, repo):
    response = client.get("/api/v1/metricas/top-tags", params={"limit": 5})
    assert response.status_code == 200
    assert response.json()["contar"] == "alarmas"
    assert response.json()["items"][0] == {
        "tag": "PT-101", "descripcion": "Presión descarga bomba P-101", "area": "Bombeo", "total": 1786,
    }
    assert repo.ultimo_filtro.limit == 5


def test_resumen_por_criticidad(client):
    body = client.get("/api/v1/metricas/por-criticidad").json()
    assert body["total"] == 40 and len(body["items"]) == 4


def test_health(client):
    assert client.get("/health").json() == {"estado": "ok", "base_de_datos": "ok"}


# --------------------------------------------------------------------------- #
# Validación de entrada (422)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("params, campo", [
    ({"desde": "ayer"}, "desde"),
    ({"desde": "2026-07-08", "hasta": "2026-07-01"}, "query"),        # rango invertido
    ({"desde": "2026-07-01", "hasta": "2026-07-01"}, "query"),        # rango vacío
    ({"criticidad": "SUPER"}, "criticidad.0"),
    ({"criticidad_min": "alta"}, "criticidad_min"),
    ({"criticidad": "HIGH", "criticidad_min": "LOW"}, "query"),       # filtros contradictorios
    ({"estado": "SHELVED"}, "estado"),
    ({"tag": "PT-10A"}, "tag"),
    ({"page": 0}, "page"),
    ({"size": 501}, "size"),
    ({"criticiad": "HIGH"}, "criticiad"),                             # parámetro mal escrito
])
def test_alarmas_parametros_invalidos(client, params, campo):
    response = client.get("/api/v1/alarmas", params=params)
    assert response.status_code == 422
    error = _error(response)
    assert error["codigo"] == "VALIDACION"
    assert campo in [d["campo"] for d in error["detalle"]]


def test_rango_invertido_explica_el_motivo(client):
    error = _error(client.get("/api/v1/alarmas", params={"desde": "2026-07-08", "hasta": "2026-07-01"}))
    assert "'desde' debe ser anterior a 'hasta'" in error["detalle"][0]["mensaje"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 51}, {"contar": "filas"}])
def test_top_tags_parametros_invalidos(client, params):
    assert client.get("/api/v1/metricas/top-tags", params=params).status_code == 422


def test_id_invalido(client):
    assert client.get("/api/v1/alarmas/abc").status_code == 422
    assert client.get("/api/v1/alarmas/0").status_code == 422


# --------------------------------------------------------------------------- #
# Otros errores
# --------------------------------------------------------------------------- #


def test_tag_inexistente_es_404(client):
    response = client.get("/api/v1/alarmas", params={"tag": "XX-999"})
    assert response.status_code == 404
    assert _error(response)["codigo"] == "NO_ENCONTRADO"


def test_evento_inexistente_es_404(client):
    assert client.get("/api/v1/alarmas/999").status_code == 404


def test_ruta_inexistente_usa_el_mismo_formato(client):
    response = client.get("/api/v1/no-existe")
    assert response.status_code == 404
    assert _error(response)["codigo"] == "HTTP_404"


def test_metodo_no_permitido(client):
    assert client.post("/api/v1/alarmas").status_code == 405


def test_bd_caida_es_503(client, repo):
    def falla(_):
        raise pyodbc.OperationalError("HYT00", "Login timeout expired")
    repo.listar = falla
    response = client.get("/api/v1/alarmas")
    assert response.status_code == 503
    assert _error(response)["codigo"] == "BD_NO_DISPONIBLE"


def test_error_inesperado_es_500_sin_detalles_internos(client, repo):
    def falla(_):
        raise RuntimeError("SELECT secreto FROM tabla_interna")
    repo.listar = falla
    response = client.get("/api/v1/alarmas")
    assert response.status_code == 500
    assert "secreto" not in response.text


# --------------------------------------------------------------------------- #
# API key
# --------------------------------------------------------------------------- #


@pytest.fixture
def client_con_clave(client):
    app.dependency_overrides[get_api_settings] = lambda: ApiSettings(api_key="clave-de-prueba", cors_origins=[])
    return client


def test_sin_api_key_es_401(client_con_clave):
    response = client_con_clave.get("/api/v1/alarmas")
    assert response.status_code == 401
    assert _error(response)["codigo"] == "NO_AUTORIZADO"


def test_api_key_incorrecta_es_401(client_con_clave):
    assert client_con_clave.get("/api/v1/alarmas", headers={"X-API-Key": "otra"}).status_code == 401


def test_api_key_correcta(client_con_clave):
    assert client_con_clave.get("/api/v1/alarmas", headers={"X-API-Key": "clave-de-prueba"}).status_code == 200


def test_health_no_requiere_api_key(client_con_clave):
    assert client_con_clave.get("/health").status_code == 200
