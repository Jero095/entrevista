from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from data_generation.generate_dataset import TAGS
from etl.catalog import AlarmaCatalogo, Catalog, load_catalog

ROOT = Path(__file__).resolve().parent.parent


def test_catalogo_coincide_con_el_generador():
    """El catálogo de la planta y el simulador deben describir los mismos instrumentos."""
    catalog = load_catalog(ROOT / "config" / "alarm_catalog.csv")
    en_catalogo = {(a.tag, a.tipo_alarma, a.limite, a.criticidad, a.unidad, a.area) for a in catalog.alarmas}
    en_generador = {(t.tag, t.alarm_type, Decimal(str(t.limit)).quantize(Decimal("0.01")), t.priority,
                     t.unit or None, t.area) for t in TAGS}
    assert en_catalogo == en_generador


def _version(limite, desde):
    return AlarmaCatalogo(tag="TT-301", descripcion="d", area="Reactor", unidad="°C", tipo_alarma="HI",
                          limite=Decimal(limite), criticidad="HIGH", vigente_desde=desde)


def test_version_vigente_segun_la_fecha_del_evento():
    enero = datetime(2026, 1, 1, tzinfo=timezone.utc)
    julio = datetime(2026, 7, 1, tzinfo=timezone.utc)
    catalog = Catalog([_version("220", julio), _version("210", enero)])

    assert catalog.version_at("TT-301", "HI", datetime(2026, 3, 15, tzinfo=timezone.utc)).limite == 210
    assert catalog.version_at("TT-301", "HI", datetime(2026, 8, 10, tzinfo=timezone.utc)).limite == 220
    assert catalog.version_at("TT-301", "HI", datetime(2025, 12, 31, tzinfo=timezone.utc)) is None

    # La vigencia de cada versión termina cuando empieza la siguiente
    assert [(v.limite, hasta) for v, hasta in catalog.versions()] == [(210, julio), (220, None)]


def test_catalogo_con_version_duplicada_falla(tmp_path):
    path = tmp_path / "catalogo.csv"
    path.write_text(
        "tag,descripcion,area,unidad,tipo_alarma,limite,criticidad,vigente_desde\n"
        "PT-101,d,Bombeo,bar,HI,8.5,HIGH,2026-01-01\n"
        "PT-101,d,Bombeo,bar,HI,9.0,HIGH,2026-01-01\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicadas"):
        load_catalog(path)


def test_catalogo_con_criticidad_invalida_falla(tmp_path):
    path = tmp_path / "catalogo.csv"
    path.write_text(
        "tag,descripcion,area,unidad,tipo_alarma,limite,criticidad,vigente_desde\n"
        "PT-101,d,Bombeo,bar,HI,8.5,ALTA,2026-01-01\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="criticidad"):
        load_catalog(path)
