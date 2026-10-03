"""Autenticación por API key (header X-API-Key) para sistemas que consumen la API."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader

from api.config import ApiSettings, get_api_settings
from api.errors import NoAutorizado

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verificar_api_key(
    key: Annotated[str | None, Security(_api_key_header)],
    settings: Annotated[ApiSettings, Depends(get_api_settings)],
) -> None:
    if settings.api_key is None:
        return
    # compare_digest tarda lo mismo sin importar dónde difieren las cadenas,
    # así un atacante no puede adivinar la clave midiendo tiempos de respuesta.
    if not secrets.compare_digest((key or "").encode(), settings.api_key.encode()):
        raise NoAutorizado()
