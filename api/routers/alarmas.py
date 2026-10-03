from typing import Annotated

from fastapi import APIRouter, Path, Query

from api.db import Repo
from api.errors import NoEncontrado
from api.schemas import AlarmaEvento, ErrorRespuesta, FiltroAlarmas, Pagina

router = APIRouter(prefix="/alarmas", tags=["Alarmas"])


@router.get(
    "",
    response_model=Pagina[AlarmaEvento],
    summary="Consultar eventos de alarma",
    responses={404: {"model": ErrorRespuesta}, 422: {"model": ErrorRespuesta}},
)
def listar_alarmas(filtros: Annotated[FiltroAlarmas, Query()], repo: Repo):
    """
    Eventos de alarma del más reciente al más antiguo, paginados.
    Todos los filtros son opcionales y se pueden combinar.
    """
    # Un tag inexistente casi siempre es un error de tipeo: 404 es más útil que una lista vacía.
    if filtros.tag and not repo.existe_tag(filtros.tag):
        raise NoEncontrado(f"El tag '{filtros.tag}' no existe")
    items, total = repo.listar(filtros)
    return Pagina[AlarmaEvento].crear(items, total, filtros.page, filtros.size)


@router.get(
    "/{id_evento}",
    response_model=AlarmaEvento,
    summary="Obtener un evento por id",
    responses={404: {"model": ErrorRespuesta}},
)
def obtener_alarma(id_evento: Annotated[int, Path(ge=1)], repo: Repo):
    evento = repo.obtener(id_evento)
    if evento is None:
        raise NoEncontrado(f"No existe el evento {id_evento}")
    return evento
