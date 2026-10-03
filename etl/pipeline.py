"""
Transformación del CSV legacy en eventos limpios + filas rechazadas.

No depende de la base de datos: recibe un DataFrame crudo y el catálogo, y
devuelve qué cargar, qué rechazar (con motivo) y estadísticas de calidad.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from etl.catalog import Catalog
from etl.normalizers import (
    InvalidValueError,
    normalize_criticidad,
    normalize_estado,
    normalize_id_evento,
    normalize_tag,
    normalize_tipo_alarma,
    normalize_timestamp,
    normalize_valor,
)

SOURCE_COLUMNS = [
    "id_evento", "timestamp", "tag", "descripcion", "area", "tipo_alarma",
    "criticidad", "estado", "valor", "limite", "unidad",
]

CLEAN_COLUMNS = [
    "id_evento_origen", "tag", "tipo_alarma", "timestamp_utc",
    "estado", "criticidad", "valor", "calidad_valor",
]


@dataclass
class TransformStats:
    leidas: int = 0
    duplicadas: int = 0
    validas: int = 0
    rechazadas: int = 0
    motivos_rechazo: Counter = field(default_factory=Counter)
    # Correcciones aplicadas (la fila se carga, pero se completó o se marcó)
    criticidad_inferida: int = 0
    tipo_alarma_inferido: int = 0
    valor_bad_quality: int = 0
    valor_vacio: int = 0
    # Avisos: el CSV contradice al catálogo; manda el catálogo
    incoherencias_limite: int = 0
    incoherencias_unidad: int = 0


@dataclass
class TransformResult:
    valid: pd.DataFrame       # columnas CLEAN_COLUMNS
    rejected: pd.DataFrame    # columnas: fila_original (JSON), motivo
    stats: TransformStats


def read_source_csv(path: Path, chunksize: int | None = None):
    """
    Lee el CSV con TODAS las columnas como texto y sin conversión automática de
    nulos: si pandas convirtiera 'NULL', 'NaN' o 'N/A' en NaN, se perdería la
    distinción entre "vacío" y "el SCADA reportó un fallo". La interpretación
    es responsabilidad de los normalizadores. 'utf-8-sig' descarta el BOM.
    """
    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
        chunksize=chunksize,
    )


def _parse_float(raw: str) -> float | None:
    try:
        return float(raw.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _transform_row(row: dict, catalog: Catalog, now: datetime, stats: TransformStats) -> tuple[dict | None, list[str]]:
    """Devuelve (evento limpio, []) o (None, [motivos de rechazo])."""
    errors: list[str] = []

    def attempt(func, raw):
        try:
            return func(raw)
        except InvalidValueError as exc:
            errors.append(str(exc))
            return None

    id_evento = attempt(normalize_id_evento, row["id_evento"])
    timestamp = attempt(lambda raw: normalize_timestamp(raw, now=now), row["timestamp"])
    tag = attempt(normalize_tag, row["tag"])
    tipo_raw = attempt(normalize_tipo_alarma, row["tipo_alarma"])
    criticidad = attempt(normalize_criticidad, row["criticidad"])
    estado = attempt(normalize_estado, row["estado"])
    valor, calidad = normalize_valor(row["valor"])

    tipo_alarma = None
    version = None
    if tag is not None:
        if not catalog.has_tag(tag):
            errors.append(f"tag no existe en el catálogo: {tag}")
        else:
            tipo_alarma = catalog.resolve_tipo(tag, tipo_raw)
            if tipo_alarma is None:
                errors.append(f"el tag {tag} no tiene configurada una alarma de tipo {row['tipo_alarma']!r}")
            elif timestamp is not None:
                version = catalog.version_at(tag, tipo_alarma, timestamp)
                if version is None:
                    errors.append(f"la alarma {tag} {tipo_alarma} no tenía configuración vigente en {timestamp:%Y-%m-%d}")

    if errors:
        return None, errors

    # --- A partir de aquí la fila es válida; se aplican correcciones y avisos ---
    if tipo_raw is None:
        stats.tipo_alarma_inferido += 1
    if criticidad is None:
        criticidad = version.criticidad
        stats.criticidad_inferida += 1
    if calidad is None:
        stats.valor_vacio += 1
    elif calidad.value == "BAD":
        stats.valor_bad_quality += 1

    limite_csv = _parse_float(row["limite"])
    if limite_csv is not None and abs(limite_csv - float(version.limite)) > 1e-6:
        stats.incoherencias_limite += 1
    if (row["unidad"].strip() or None) != version.unidad:
        stats.incoherencias_unidad += 1

    return {
        "id_evento_origen": id_evento,
        "tag": tag,
        "tipo_alarma": tipo_alarma,
        "timestamp_utc": timestamp,
        "estado": estado,
        "criticidad": criticidad,
        "valor": valor,
        "calidad_valor": calidad.value if calidad else None,
    }, []


def transform(raw: pd.DataFrame, catalog: Catalog, now: datetime | None = None) -> TransformResult:
    missing = set(SOURCE_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"al CSV le faltan columnas: {sorted(missing)}")

    stats = TransformStats(leidas=len(raw))

    # El SCADA a veces reenvía el mismo evento: se conserva la primera aparición.
    duplicated = raw["id_evento"].str.strip().duplicated(keep="first") & (raw["id_evento"].str.strip() != "")
    stats.duplicadas = int(duplicated.sum())
    rows = raw.loc[~duplicated, SOURCE_COLUMNS].to_dict("records")

    now = now or pd.Timestamp.now(tz="UTC").to_pydatetime()
    valid: list[dict] = []
    rejected: list[dict] = []
    for row in rows:
        event, errors = _transform_row(row, catalog, now, stats)
        if event is not None:
            valid.append(event)
        else:
            rejected.append({
                "fila_original": json.dumps(row, ensure_ascii=False),
                "motivo": "; ".join(errors),
            })
            # Para las estadísticas basta el tipo de error, sin el valor concreto.
            stats.motivos_rechazo.update(e.split(":")[0] for e in errors)

    stats.validas = len(valid)
    stats.rechazadas = len(rejected)
    return TransformResult(
        valid=pd.DataFrame(valid, columns=CLEAN_COLUMNS),
        rejected=pd.DataFrame(rejected, columns=["fila_original", "motivo"]),
        stats=stats,
    )
