"""Conversión de los eventos limpios a parámetros del driver (sin base de datos)."""

from datetime import datetime, timezone

import pandas as pd

from etl.loader import event_rows
from etl.pipeline import CLEAN_COLUMNS


def test_nulos_de_pandas_se_envian_como_none_y_fechas_sin_zona():
    valid = pd.DataFrame([
        {"id_evento_origen": 1, "tag": "PT-101", "tipo_alarma": "HI",
         "timestamp_utc": datetime(2026, 7, 2, 0, 11, 4, 278_000, tzinfo=timezone.utc),
         "estado": "ACTIVE", "criticidad": "HIGH", "valor": 8.8, "calidad_valor": "GOOD"},
        {"id_evento_origen": 2, "tag": "PT-101", "tipo_alarma": "HI",
         "timestamp_utc": datetime(2026, 7, 2, 0, 12, tzinfo=timezone.utc),
         "estado": "ACK", "criticidad": "HIGH", "valor": None, "calidad_valor": None},
    ], columns=CLEAN_COLUMNS)

    first, second = event_rows(valid)

    assert first == (1, "PT-101", "HI", datetime(2026, 7, 2, 0, 11, 4, 278_000), "ACTIVE", "HIGH", 8.8, "GOOD")
    assert type(first[3]) is datetime and first[3].tzinfo is None
    assert second[6] is None and second[7] is None
