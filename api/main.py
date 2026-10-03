"""
Punto de entrada de la API.

    uvicorn api.main:app --reload
    Documentación interactiva: http://localhost:8000/docs
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_api_settings
from api.db import Repo
from api.errors import registrar_manejadores
from api.routers import alarmas, metricas, tags
from api.security import verificar_api_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s %(message)s")

app = FastAPI(
    title="API de alarmas SCADA",
    version="1.0.0",
    description=(
        "Consulta del histórico de alarmas de planta, normalizado desde exportaciones legacy. "
        "Fechas en UTC (ISO 8601). Si la API tiene clave, enviarla en el header `X-API-Key`."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_api_settings().cors_origins,
    allow_methods=["GET"],          # la API es de solo lectura
    allow_headers=["X-API-Key"],
)
registrar_manejadores(app)

# Versión en la URL: si un cambio rompe el contrato se publica /api/v2 sin
# afectar a los sistemas de planta que ya consumen /api/v1.
api_v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(verificar_api_key)])
api_v1.include_router(alarmas.router)
api_v1.include_router(metricas.router)
api_v1.include_router(tags.router)
app.include_router(api_v1)


@app.get("/health", tags=["Salud"], summary="Estado de la API y de la base de datos")
def health(repo: Repo):
    """No requiere API key: lo usan Docker y los balanceadores para saber si el servicio responde."""
    repo.ping()
    return {"estado": "ok", "base_de_datos": "ok"}
