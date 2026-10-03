from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest

from etl.catalog import AlarmaCatalogo, Catalog
from etl.pipeline import transform

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
DESDE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _alarma(tag, tipo, limite, criticidad, unidad="bar", desde=DESDE):
    return AlarmaCatalogo(tag=tag, descripcion=f"desc {tag}", area="Bombeo", unidad=unidad,
                          tipo_alarma=tipo, limite=Decimal(limite), criticidad=criticidad,
                          vigente_desde=desde)


@pytest.fixture
def catalog():
    return Catalog([
        _alarma("PT-101", "HI", "8.5", "HIGH"),
        _alarma("PT-101", "HIHI", "10", "CRITICAL"),   # mismo tag, dos alarmas
        _alarma("FT-201", "LO", "80", "MEDIUM", unidad="m3/h"),
    ])


def _row(**overrides):
    row = {
        "id_evento": "1", "timestamp": "2026-07-02T00:00:00Z", "tag": "FT-201",
        "descripcion": "x", "area": "Tanques", "tipo_alarma": "LO", "criticidad": "MEDIUM",
        "estado": "ACTIVE", "valor": "79.0", "limite": "80.00", "unidad": "m3/h",
    }
    row.update(overrides)
    return row


def _run(catalog, *rows):
    return transform(pd.DataFrame(list(rows)), catalog, now=NOW)


def test_fila_limpia_se_carga(catalog):
    result = _run(catalog, _row())
    assert result.stats.validas == 1
    event = result.valid.iloc[0]
    assert event.tag == "FT-201"
    assert event.timestamp_utc == datetime(2026, 7, 2, tzinfo=timezone.utc)
    assert event.calidad_valor == "GOOD"


def test_duplicados_exactos_se_eliminan(catalog):
    result = _run(catalog, _row(), _row(), _row(id_evento="2"))
    assert result.stats.duplicadas == 1
    assert result.stats.validas == 2


def test_fila_sucia_pero_recuperable_se_normaliza(catalog):
    result = _run(catalog, _row(tag=" ft_201 ", criticidad="Media", estado="ACT", valor="79,5",
                                timestamp="01/07/2026 19:00:00"))
    event = result.valid.iloc[0]
    assert (event.tag, event.criticidad, event.estado, event.valor) == ("FT-201", "MEDIUM", "ACTIVE", 79.5)
    assert event.timestamp_utc == datetime(2026, 7, 2, tzinfo=timezone.utc)


def test_criticidad_vacia_se_toma_del_catalogo(catalog):
    result = _run(catalog, _row(tag="PT-101", tipo_alarma="HIHI", criticidad="", limite="10", unidad="bar"))
    assert result.valid.iloc[0].criticidad == "CRITICAL"
    assert result.stats.criticidad_inferida == 1


def test_tipo_vacio_se_infiere_si_el_tag_tiene_una_sola_alarma(catalog):
    result = _run(catalog, _row(tipo_alarma=""))
    assert result.valid.iloc[0].tipo_alarma == "LO"
    assert result.stats.tipo_alarma_inferido == 1


def test_tipo_vacio_es_ambiguo_si_el_tag_tiene_varias_alarmas(catalog):
    result = _run(catalog, _row(tag="PT-101", tipo_alarma=""))
    assert result.stats.rechazadas == 1


def test_valor_bad_quality_no_rechaza_la_fila(catalog):
    result = _run(catalog, _row(valor="Bad Quality"))
    event = result.valid.iloc[0]
    assert pd.isna(event.valor)
    assert event.calidad_valor == "BAD"


def test_rechazo_acumula_todos_los_motivos(catalog):
    result = _run(catalog, _row(timestamp="N/A", tag=""))
    assert result.stats.rechazadas == 1
    motivo = result.rejected.iloc[0].motivo
    assert "timestamp" in motivo and "tag vacío" in motivo


def test_rechazo_conserva_la_fila_original(catalog):
    result = _run(catalog, _row(timestamp="N/A"))
    assert '"timestamp": "N/A"' in result.rejected.iloc[0].fila_original


def test_tag_fuera_del_catalogo_se_rechaza(catalog):
    result = _run(catalog, _row(tag="XX-999"))
    assert "no existe en el catálogo" in result.rejected.iloc[0].motivo


def test_evento_anterior_a_la_configuracion_se_rechaza(catalog):
    result = _run(catalog, _row(timestamp="2025-06-01T00:00:00Z"))
    assert "configuración vigente" in result.rejected.iloc[0].motivo


def test_limite_del_csv_distinto_al_catalogo_genera_aviso(catalog):
    result = _run(catalog, _row(limite="75.00"))
    assert result.stats.validas == 1
    assert result.stats.incoherencias_limite == 1


def test_faltan_columnas_falla_rapido(catalog):
    with pytest.raises(ValueError, match="faltan columnas"):
        transform(pd.DataFrame([{"id_evento": "1"}]), catalog, now=NOW)
