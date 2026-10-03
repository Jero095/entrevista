"""
Manejo de errores centralizado. Toda respuesta de error tiene la misma forma:

    {"error": {"codigo": "VALIDACION", "mensaje": "...", "detalle": [...] | null}}

así los sistemas que consumen la API pueden procesar errores sin casos especiales.
Los errores internos se registran en el log, pero al cliente no se le exponen
detalles (trazas, SQL, nombres de tablas).
"""

from __future__ import annotations

import logging

import pyodbc
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("api")


class ApiError(Exception):
    def __init__(self, status_code: int, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.status_code = status_code
        self.codigo = codigo
        self.mensaje = mensaje


class NoEncontrado(ApiError):
    def __init__(self, mensaje: str):
        super().__init__(404, "NO_ENCONTRADO", mensaje)


class NoAutorizado(ApiError):
    def __init__(self, mensaje: str = "API key inválida o ausente"):
        super().__init__(401, "NO_AUTORIZADO", mensaje)


def _respuesta(status_code: int, codigo: str, mensaje: str, detalle: list | None = None,
               headers: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"codigo": codigo, "mensaje": mensaje, "detalle": detalle}},
        headers=headers,
    )


def _campo(loc: tuple) -> str:
    # loc = ("query", "criticidad", 0) -> "criticidad.0"; errores del modelo completo -> "query"
    partes = [str(p) for p in loc[1:]]
    return ".".join(partes) if partes else str(loc[0])


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        detalle = [{"campo": _campo(e["loc"]), "mensaje": e["msg"]} for e in exc.errors()]
        return _respuesta(422, "VALIDACION", "Parámetros inválidos", detalle)

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        headers = {"WWW-Authenticate": "ApiKey"} if exc.status_code == 401 else None
        return _respuesta(exc.status_code, exc.codigo, exc.mensaje, headers=headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Rutas inexistentes (404), métodos no permitidos (405)...
        return _respuesta(exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail))

    @app.exception_handler(pyodbc.OperationalError)
    @app.exception_handler(pyodbc.InterfaceError)
    async def _bd_no_disponible(request: Request, exc: pyodbc.Error) -> JSONResponse:
        # Servidor caído, timeout o credenciales rechazadas: no es culpa del cliente.
        log.exception("Base de datos no disponible")
        return _respuesta(503, "BD_NO_DISPONIBLE", "La base de datos no está disponible. Intente más tarde.")

    @app.exception_handler(Exception)
    async def _interno(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Error no controlado en %s", request.url.path)
        return _respuesta(500, "ERROR_INTERNO", "Error interno del servidor")
