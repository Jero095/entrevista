"""
Normalizadores por columna del CSV legacy.

Cada función recibe el texto crudo de una celda y devuelve el valor canónico, o
lanza InvalidValueError con un motivo legible cuando el dato no tiene arreglo.
Son funciones puras (sin pandas ni base de datos) para poder probarlas caso a caso.

Criterio general:
- Se ARREGLA lo que tiene una única interpretación razonable (formatos de fecha
  conocidos, sinónimos, coma decimal).
- Se RECHAZA lo que obligaría a inventar datos (fecha "N/A", tag vacío).
- NO se adivina: las fechas se parsean contra una lista explícita de formatos,
  nunca con un parser "inteligente" que podría confundir día y mes en silencio.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from enum import Enum

UTC = timezone.utc
# Hora local de la planta (supuesto documentado en docs/dataset.md).
PLANT_TZ = timezone(timedelta(hours=-5))

# Fechas anteriores a esto se consideran basura (p. ej. relojes de PLC reseteados a 1970).
MIN_VALID_TIMESTAMP = datetime(2000, 1, 1, tzinfo=UTC)
# Tolerancia para desfases de reloj entre el SCADA y el servidor de ingesta.
FUTURE_TOLERANCE = timedelta(minutes=5)


class InvalidValueError(ValueError):
    """El valor de una celda no se puede normalizar; el mensaje es el motivo de rechazo."""


class Calidad(str, Enum):
    GOOD = "GOOD"
    BAD = "BAD"


def _clean(raw: str | None) -> str:
    return "" if raw is None else str(raw).strip()


# --------------------------------------------------------------------------- #
# Timestamp
# --------------------------------------------------------------------------- #

# (formato strptime, zona horaria asumida). El orden no importa: los formatos son
# mutuamente excluyentes por sus separadores, así que a lo sumo uno coincide.
_TIMESTAMP_FORMATS: list[tuple[str, timezone]] = [
    ("%Y-%m-%dT%H:%M:%SZ", UTC),            # 2026-07-02T00:12:14Z
    ("%Y%m%dT%H%M%SZ", UTC),                # 20260702T010413Z (ISO 8601 básico)
    ("%Y-%m-%d %H:%M:%S", UTC),             # 2026-07-02 00:26:21 (servidor histórico, UTC)
    ("%Y/%m/%d %H:%M:%S.%f", UTC),          # 2026/07/02 00:11:04.278 (servidor histórico, UTC)
    ("%d/%m/%Y %H:%M:%S", PLANT_TZ),        # 01/07/2026 19:01:13 (HMI local, día primero)
    ("%m-%d-%Y %I:%M:%S %p", PLANT_TZ),     # 07-01-2026 07:11:05 PM (HMI local, estilo US)
]

_EPOCH_SECONDS = re.compile(r"^\d{10}$")
_EPOCH_MILLIS = re.compile(r"^\d{13}$")
_ISO_WITH_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}$")


def _parse_timestamp(text: str) -> datetime:
    if _EPOCH_SECONDS.match(text):
        return datetime.fromtimestamp(int(text), tz=UTC)
    if _EPOCH_MILLIS.match(text):
        return datetime.fromtimestamp(int(text) / 1000, tz=UTC)
    if _ISO_WITH_OFFSET.match(text):
        return datetime.fromisoformat(text).astimezone(UTC)

    for fmt, tz in _TIMESTAMP_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=tz).astimezone(UTC)

    raise InvalidValueError(f"timestamp con formato no reconocido o fecha imposible: {text!r}")


def normalize_timestamp(raw: str | None, now: datetime | None = None) -> datetime:
    """Devuelve el instante en UTC (datetime con tzinfo=UTC)."""
    text = _clean(raw)
    if not text:
        raise InvalidValueError("timestamp vacío")

    ts = _parse_timestamp(text)

    now = now or datetime.now(UTC)
    if ts < MIN_VALID_TIMESTAMP:
        raise InvalidValueError(f"timestamp anterior a {MIN_VALID_TIMESTAMP:%Y-%m-%d}: {text!r}")
    if ts > now + FUTURE_TOLERANCE:
        raise InvalidValueError(f"timestamp en el futuro: {text!r}")
    return ts


# --------------------------------------------------------------------------- #
# Tag
# --------------------------------------------------------------------------- #

# Nomenclatura ISA: 2 letras (variable + función) + número de lazo.
# Acepta separador '-', '_', espacio o ninguno: 'PT-101', 'pt_101', 'tt 301', 'PT101'.
_TAG_PATTERN = re.compile(r"^([A-Z]{2})[\s_-]?(\d{3})$")


def normalize_tag(raw: str | None) -> str:
    """Devuelve el tag en formato canónico 'XX-NNN'."""
    text = _clean(raw).upper()
    if not text:
        raise InvalidValueError("tag vacío")
    match = _TAG_PATTERN.match(text)
    if not match:
        raise InvalidValueError(f"tag con formato inválido: {raw!r}")
    return f"{match.group(1)}-{match.group(2)}"


# --------------------------------------------------------------------------- #
# Tipo de alarma
# --------------------------------------------------------------------------- #

TIPOS_ALARMA = {"HI", "HIHI", "LO", "LOLO", "DEV", "ROC", "DISC"}


def normalize_tipo_alarma(raw: str | None) -> str | None:
    """Devuelve el tipo canónico, o None si viene vacío (se intentará inferir del catálogo)."""
    text = _clean(raw).upper()
    if not text:
        return None
    if text == "DSC":  # abreviatura usada por algunos SCADA para discretas
        text = "DISC"
    if text not in TIPOS_ALARMA:
        raise InvalidValueError(f"tipo de alarma desconocido: {raw!r}")
    return text


# --------------------------------------------------------------------------- #
# Criticidad
# --------------------------------------------------------------------------- #

# Sinónimos observados en la fuente. La numeración sigue la convención de
# prioridad del SCADA: 1 = la más urgente.
_CRITICIDAD_SYNONYMS: dict[str, str] = {
    **dict.fromkeys(["critical", "crit", "crítica", "critica", "p1", "1", "urgent"], "CRITICAL"),
    **dict.fromkeys(["high", "hi", "alta", "p2", "2"], "HIGH"),
    **dict.fromkeys(["medium", "med", "media", "p3", "3"], "MEDIUM"),
    **dict.fromkeys(["low", "lo", "baja", "p4", "4"], "LOW"),
}

CRITICIDADES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def normalize_criticidad(raw: str | None) -> str | None:
    """Devuelve la criticidad canónica, o None si viene vacía (se completará desde el catálogo)."""
    text = _clean(raw).casefold()
    if not text:
        return None
    try:
        return _CRITICIDAD_SYNONYMS[text]
    except KeyError:
        raise InvalidValueError(f"criticidad desconocida: {raw!r}") from None


# --------------------------------------------------------------------------- #
# Estado del ciclo de vida
# --------------------------------------------------------------------------- #

_ESTADO_SYNONYMS: dict[str, str] = {
    **dict.fromkeys(["active", "act", "alm", "unack_alm"], "ACTIVE"),
    **dict.fromkeys(["ack", "acknowledged", "acked", "ack_alm"], "ACK"),
    **dict.fromkeys(["rtn", "return", "rtn_unack", "cleared", "normal", "ok"], "RTN"),
}


def normalize_estado(raw: str | None) -> str:
    text = _clean(raw).casefold()
    if not text:
        raise InvalidValueError("estado vacío")
    try:
        return _ESTADO_SYNONYMS[text]
    except KeyError:
        raise InvalidValueError(f"estado desconocido: {raw!r}") from None


# --------------------------------------------------------------------------- #
# Valor del proceso
# --------------------------------------------------------------------------- #


def normalize_valor(raw: str | None) -> tuple[float | None, Calidad | None]:
    """
    Devuelve (valor, calidad). Nunca rechaza la fila: un evento de alarma sigue
    siendo válido aunque la lectura del sensor no lo sea.

    - ''                      -> (None, None)  la fuente no trajo valor
    - '85,30', '2.442e+01'    -> (85.3, GOOD)
    - 'Bad Quality', 'NaN'... -> (None, BAD)   el SCADA marcó la lectura como no confiable
    """
    text = _clean(raw)
    if not text:
        return None, None
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        return None, Calidad.BAD
    if math.isnan(value) or math.isinf(value):
        return None, Calidad.BAD
    return value, Calidad.GOOD


# --------------------------------------------------------------------------- #
# Id del evento en el sistema origen
# --------------------------------------------------------------------------- #


def normalize_id_evento(raw: str | None) -> int:
    text = _clean(raw)
    if not text.isdigit() or int(text) == 0:
        raise InvalidValueError(f"id_evento inválido: {raw!r}")
    return int(text)
