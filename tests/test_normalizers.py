"""Casos borde de cada defecto documentado en docs/dataset.md."""

from datetime import datetime, timezone

import pytest

from etl.normalizers import (
    Calidad,
    InvalidValueError,
    normalize_criticidad,
    normalize_estado,
    normalize_id_evento,
    normalize_tag,
    normalize_timestamp,
    normalize_tipo_alarma,
    normalize_valor,
)

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
# El mismo instante (2026-07-02 00:11:04 UTC) en todos los formatos de la fuente.
EXPECTED = datetime(2026, 7, 2, 0, 11, 4, tzinfo=timezone.utc)


@pytest.mark.parametrize("raw", [
    "2026-07-02T00:11:04Z",               # ISO UTC
    "20260702T001104Z",                   # ISO básico
    "2026-07-02 00:11:04",                # sin zona: servidor histórico en UTC
    "2026-07-01T19:11:04.000-05:00",      # ISO con offset de la planta
    "01/07/2026 19:11:04",                # HMI local, día primero (UTC-5)
    "07-01-2026 07:11:04 PM",             # HMI local, estilo US con AM/PM (UTC-5)
    "1782951064",                         # epoch en segundos
    "1782951064000",                      # epoch en milisegundos
    "  2026-07-02T00:11:04Z\t",           # espacios alrededor
])
def test_timestamp_formatos_equivalentes(raw):
    assert normalize_timestamp(raw, now=NOW) == EXPECTED


def test_timestamp_con_milisegundos():
    result = normalize_timestamp("2026/07/02 00:11:04.278", now=NOW)
    assert result == EXPECTED.replace(microsecond=278_000)


def test_timestamp_devuelve_utc_con_zona():
    assert normalize_timestamp("01/07/2026 19:11:04", now=NOW).tzinfo == timezone.utc


@pytest.mark.parametrize("raw", [
    "N/A", "ERR", "##########",
    "0000-00-00 00:00:00",    # fecha cero de algunos PLC
    "31/02/2026 10:00:00",    # día inexistente
    "2026-13-01 00:00:00",    # mes inexistente
    "02-07-2026 00:11:04",    # estilo US sin AM/PM: no es un formato conocido, no se adivina
])
def test_timestamp_invalido_se_rechaza(raw):
    with pytest.raises(InvalidValueError):
        normalize_timestamp(raw, now=NOW)


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_timestamp_vacio_se_rechaza(raw):
    with pytest.raises(InvalidValueError, match="vacío"):
        normalize_timestamp(raw, now=NOW)


def test_timestamp_en_el_futuro_se_rechaza():
    with pytest.raises(InvalidValueError, match="futuro"):
        normalize_timestamp("2026-12-31T00:00:00Z", now=NOW)


def test_timestamp_con_desfase_de_reloj_tolerado():
    assert normalize_timestamp("2026-10-01T00:03:00Z", now=NOW)


def test_timestamp_epoch_antiguo_se_rechaza():
    with pytest.raises(InvalidValueError, match="anterior"):
        normalize_timestamp("0000000001", now=NOW)


@pytest.mark.parametrize("raw", ["PT-101", "pt-101", " PT-101 ", "PT-101\t", "PT_101", "PT101", "pt 101"])
def test_tag_variantes_se_normalizan(raw):
    assert normalize_tag(raw) == "PT-101"


@pytest.mark.parametrize("raw", ["PT-10", "P-101", "PT--101", "101", "PT-101-A"])
def test_tag_formato_invalido_se_rechaza(raw):
    with pytest.raises(InvalidValueError, match="formato"):
        normalize_tag(raw)


@pytest.mark.parametrize("raw", ["", "  ", None])
def test_tag_vacio_se_rechaza(raw):
    with pytest.raises(InvalidValueError, match="vacío"):
        normalize_tag(raw)


@pytest.mark.parametrize("raw, expected", [
    ("CRITICAL", "CRITICAL"), ("crit", "CRITICAL"), ("Crítica", "CRITICAL"), ("P1", "CRITICAL"),
    ("1", "CRITICAL"), ("Urgent", "CRITICAL"),
    ("high", "HIGH"), ("Alta", "HIGH"), ("HI", "HIGH"), ("2", "HIGH"),
    ("Media", "MEDIUM"), ("MED", "MEDIUM"), ("p3", "MEDIUM"),
    ("Baja", "LOW"), ("LO", "LOW"), (" 4 ", "LOW"),
])
def test_criticidad_sinonimos(raw, expected):
    assert normalize_criticidad(raw) == expected


def test_criticidad_vacia_devuelve_none_para_inferir():
    assert normalize_criticidad("") is None


def test_criticidad_desconocida_se_rechaza():
    with pytest.raises(InvalidValueError):
        normalize_criticidad("SUPER")


@pytest.mark.parametrize("raw, expected", [
    ("ACTIVE", "ACTIVE"), ("Active", "ACTIVE"), ("ACT", "ACTIVE"), ("ALM", "ACTIVE"), ("UNACK_ALM", "ACTIVE"),
    ("ACK", "ACK"), ("Acknowledged", "ACK"), ("ACKED", "ACK"), ("ACK_ALM", "ACK"),
    ("RTN", "RTN"), ("Return", "RTN"), ("RTN_UNACK", "RTN"), ("Cleared", "RTN"), ("NORMAL", "RTN"), ("OK", "RTN"),
])
def test_estado_sinonimos(raw, expected):
    assert normalize_estado(raw) == expected


@pytest.mark.parametrize("raw", ["", "SHELVED"])
def test_estado_vacio_o_desconocido_se_rechaza(raw):
    with pytest.raises(InvalidValueError):
        normalize_estado(raw)


@pytest.mark.parametrize("raw, expected", [
    ("85.30", 85.3),
    ("85,30", 85.3),             # coma decimal
    ("2.442e+01", 24.42),        # notación científica
    ("6.960000  ", 6.96),        # espacios y exceso de precisión
    ("-3.5", -3.5),
    ("0", 0.0),
])
def test_valor_numerico(raw, expected):
    value, calidad = normalize_valor(raw)
    assert value == pytest.approx(expected)
    assert calidad is Calidad.GOOD


@pytest.mark.parametrize("raw", ["Bad Quality", "#####", "NaN", "nan", "COMM FAIL", "---", "inf"])
def test_valor_mala_calidad(raw):
    assert normalize_valor(raw) == (None, Calidad.BAD)


def test_valor_vacio_no_es_mala_calidad():
    assert normalize_valor("") == (None, None)


@pytest.mark.parametrize("raw, expected", [("HI", "HI"), (" hihi ", "HIHI"), ("DSC", "DISC"), ("", None)])
def test_tipo_alarma(raw, expected):
    assert normalize_tipo_alarma(raw) == expected


def test_tipo_alarma_desconocido_se_rechaza():
    with pytest.raises(InvalidValueError):
        normalize_tipo_alarma("XYZ")


@pytest.mark.parametrize("raw", ["", "abc", "-1", "0", "1.5"])
def test_id_evento_invalido(raw):
    with pytest.raises(InvalidValueError):
        normalize_id_evento(raw)


def test_id_evento_valido():
    assert normalize_id_evento(" 42 ") == 42
