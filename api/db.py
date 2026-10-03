"""Dependencias de FastAPI para obtener la conexión y el repositorio."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

import pyodbc
from fastapi import Depends

from api.config import get_db_settings
from api.repository import AlarmaRepository


def get_connection() -> Iterator[pyodbc.Connection]:
    """
    Una conexión por request. pyodbc mantiene un pool de conexiones: close()
    devuelve la conexión al pool en lugar de cerrarla, así que no se paga el
    costo de abrir una conexión nueva en cada petición.
    """
    conn = pyodbc.connect(get_db_settings().connection_string(), timeout=5)
    try:
        yield conn
    finally:
        conn.close()


def get_repository(conn: Annotated[pyodbc.Connection, Depends(get_connection)]) -> AlarmaRepository:
    return AlarmaRepository(conn)


Repo = Annotated[AlarmaRepository, Depends(get_repository)]
