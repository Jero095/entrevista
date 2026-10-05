from typing import Annotated

from fastapi import APIRouter, Query

from api.db import Repo
from api.errors import NoEncontrado
from api.schemas import ErrorRespuesta, LoteCarga, RechazosLote

router = APIRouter(prefix="/etl", tags=["Calidad de datos (ETL)"], responses={422: {"model": ErrorRespuesta}})


@router.get("/lotes", response_model=list[LoteCarga], summary="Ejecuciones del ETL")
def listar_lotes(repo: Repo, limit: Annotated[int, Query(ge=1, le=100, description="Cantidad de lotes")] = 10):
    """Resumen de cada carga: filas leídas, duplicadas, cargadas y rechazadas. La más reciente primero."""
    return repo.lotes(limit)


@router.get(
    "/rechazados",
    response_model=RechazosLote,
    summary="Filas rechazadas por el ETL",
    responses={404: {"model": ErrorRespuesta}},
)
def listar_rechazados(
    repo: Repo,
    lote_id: Annotated[
        int | None, Query(ge=1, description="Lote a consultar; por defecto, la última carga exitosa")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Cantidad de filas de muestra")] = 20,
):
    """Motivos de rechazo agrupados y una muestra de las filas tal como venían en el CSV."""
    if lote_id is None:
        lote_id = repo.ultimo_lote_ok()
        if lote_id is None:
            raise NoEncontrado("Todavía no hay cargas exitosas registradas")
    resultado = repo.rechazos(lote_id, limit)
    if resultado is None:
        raise NoEncontrado(f"No existe el lote {lote_id}")
    return resultado
