"""Configuración propia de la API (la de la base de datos se comparte con el ETL)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from etl.settings import DbSettings


@dataclass(frozen=True)
class ApiSettings:
    api_key: str | None
    cors_origins: list[str]

    @classmethod
    def from_env(cls) -> ApiSettings:
        origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
        return cls(
            # Sin API_KEY la API queda abierta (útil en desarrollo); en planta se define siempre.
            api_key=os.environ.get("API_KEY") or None,
            cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        )


@lru_cache
def get_api_settings() -> ApiSettings:
    return ApiSettings.from_env()


@lru_cache
def get_db_settings() -> DbSettings:
    # Se lee al primer uso, no al importar: los tests reemplazan la BD y no la necesitan.
    return DbSettings.for_api()
