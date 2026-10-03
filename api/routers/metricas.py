from typing import Annotated

from fastapi import APIRouter, Query

from api.db import Repo
from api.schemas import ErrorRespuesta, FiltroResumen, FiltroTopTags, ResumenCriticidad, TopTagsRespuesta

router = APIRouter(prefix="/metricas", tags=["Métricas"], responses={422: {"model": ErrorRespuesta}})


@router.get("/top-tags", response_model=TopTagsRespuesta, summary="Tags con más alarmas")
def top_tags(filtros: Annotated[FiltroTopTags, Query()], repo: Repo):
    """
    Ranking de tags por número de alarmas. Los primeros suelen ser los "bad actors"
    (ISA-18.2): pocos instrumentos que generan la mayoría de las alarmas y son los
    primeros candidatos a revisar.
    """
    return TopTagsRespuesta(
        contar=filtros.contar, desde=filtros.desde, hasta=filtros.hasta, items=repo.top_tags(filtros),
    )


@router.get("/por-criticidad", response_model=ResumenCriticidad, summary="Alarmas por criticidad")
def por_criticidad(filtros: Annotated[FiltroResumen, Query()], repo: Repo):
    items = repo.por_criticidad(filtros)
    return ResumenCriticidad(
        desde=filtros.desde, hasta=filtros.hasta, total=sum(i["total"] for i in items), items=items,
    )
