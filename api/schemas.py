"""
Contrato de la API: qué entra (filtros validados) y qué sale (modelos de respuesta).

Toda la validación de entrada vive aquí. Si un parámetro no cumple, FastAPI
responde 422 antes de que se ejecute el endpoint o se toque la base de datos.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from etl.normalizers import normalize_tag


class Criticidad(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Debe coincidir con dbo.criticidad.nivel
NIVEL: dict[Criticidad, int] = {
    Criticidad.LOW: 1, Criticidad.MEDIUM: 2, Criticidad.HIGH: 3, Criticidad.CRITICAL: 4,
}


class Estado(str, Enum):
    ACTIVE = "ACTIVE"
    ACK = "ACK"
    RTN = "RTN"


def _a_utc(value: datetime | None) -> datetime | None:
    """Las fechas sin zona se interpretan como UTC, que es como las guarda la BD."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# --------------------------------------------------------------------------- #
# Entrada
# --------------------------------------------------------------------------- #


class FiltroTiempo(BaseModel):
    # Un parámetro desconocido (p. ej. ?criticiad=HIGH) responde 422 en lugar de
    # ignorarse en silencio y devolver datos sin filtrar.
    model_config = ConfigDict(extra="forbid")

    desde: datetime | None = Field(
        None, description="Inicio del rango, incluido. ISO 8601; sin zona horaria se asume UTC.",
        examples=["2026-07-01T00:00:00Z"],
    )
    hasta: datetime | None = Field(
        None, description="Fin del rango, excluido. ISO 8601; sin zona horaria se asume UTC.",
        examples=["2026-07-08T00:00:00Z"],
    )

    _utc = field_validator("desde", "hasta")(_a_utc)

    @model_validator(mode="after")
    def _rango_valido(self):
        if self.desde and self.hasta and self.desde >= self.hasta:
            raise ValueError("'desde' debe ser anterior a 'hasta'")
        return self


class FiltroAlarmas(FiltroTiempo):
    tag: str | None = Field(
        None, description="Código del instrumento. Acepta variantes como 'pt_101' o 'PT101'.",
        examples=["PT-101"],
    )
    criticidad: list[Criticidad] | None = Field(
        None, description="Una o varias criticidades exactas: ?criticidad=HIGH&criticidad=CRITICAL",
    )
    criticidad_min: Criticidad | None = Field(None, description="Esta criticidad o superior")
    estado: Estado | None = Field(None, description="Transición del ciclo de vida de la alarma")
    page: int = Field(1, ge=1, description="Número de página, desde 1")
    size: int = Field(50, ge=1, le=500, description="Eventos por página (máximo 500)")

    @field_validator("tag")
    @classmethod
    def _normalizar_tag(cls, value: str | None) -> str | None:
        # Misma regla que usa el ETL para limpiar la fuente.
        return normalize_tag(value) if value is not None else None

    @model_validator(mode="after")
    def _criticidad_excluyente(self):
        if self.criticidad and self.criticidad_min:
            raise ValueError("use 'criticidad' o 'criticidad_min', no ambos")
        return self


class FiltroTopTags(FiltroTiempo):
    limit: int = Field(10, ge=1, le=50, description="Cantidad de tags a devolver (máximo 50)")
    contar: Literal["alarmas", "eventos"] = Field(
        "alarmas",
        description=(
            "'alarmas' cuenta solo los eventos ACTIVE (veces que saltó la alarma); "
            "'eventos' cuenta todas las transiciones (ACTIVE, ACK y RTN)."
        ),
    )
    criticidad_min: Criticidad | None = Field(None, description="Esta criticidad o superior")


class FiltroResumen(FiltroTiempo):
    pass


# --------------------------------------------------------------------------- #
# Salida
# --------------------------------------------------------------------------- #


class AlarmaEvento(BaseModel):
    id: int
    id_evento_origen: int = Field(description="Id del evento en el SCADA de origen")
    timestamp_utc: datetime
    tag: str
    descripcion: str
    area: str
    tipo_alarma: str
    criticidad: Criticidad
    estado: Estado
    valor: float | None = Field(description="Lectura del sensor; null si no llegó o no era confiable")
    calidad_valor: Literal["GOOD", "BAD"] | None
    unidad: str | None
    limite: float = Field(description="Límite vigente cuando ocurrió el evento")
    desviacion_limite: float | None = Field(description="valor - limite")

    # La BD devuelve fechas UTC sin zona; se marcan como UTC para que el JSON lleve 'Z'.
    _utc = field_validator("timestamp_utc")(_a_utc)


T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(description="Total de resultados que cumplen los filtros")
    page: int
    size: int
    pages: int

    @classmethod
    def crear(cls, items: list[Any], total: int, page: int, size: int) -> Pagina:
        return cls(items=items, total=total, page=page, size=size, pages=math.ceil(total / size))


class TopTag(BaseModel):
    tag: str
    descripcion: str
    area: str
    total: int


class TopTagsRespuesta(BaseModel):
    contar: Literal["alarmas", "eventos"]
    desde: datetime | None
    hasta: datetime | None
    items: list[TopTag]


class ConteoCriticidad(BaseModel):
    criticidad: Criticidad
    nivel: int
    total: int


class ResumenCriticidad(BaseModel):
    desde: datetime | None
    hasta: datetime | None
    total: int = Field(description="Alarmas (eventos ACTIVE) en el rango")
    items: list[ConteoCriticidad]


class AlarmaConfigurada(BaseModel):
    tipo_alarma: str
    limite: float
    criticidad: Criticidad
    vigente_desde: datetime


class TagCatalogo(BaseModel):
    tag: str
    descripcion: str
    area: str
    unidad: str | None
    alarmas: list[AlarmaConfigurada]


class ErrorCampo(BaseModel):
    campo: str
    mensaje: str


class ErrorDetalle(BaseModel):
    codigo: str = Field(examples=["VALIDACION"])
    mensaje: str
    detalle: list[ErrorCampo] | None = None


class ErrorRespuesta(BaseModel):
    error: ErrorDetalle
