from fastapi import APIRouter

from api.db import Repo
from api.schemas import TagCatalogo

router = APIRouter(prefix="/tags", tags=["Catálogo"])


@router.get("", response_model=list[TagCatalogo], summary="Catálogo de instrumentos y alarmas")
def listar_tags(repo: Repo):
    """Instrumentos con su unidad, área y la configuración vigente de cada alarma."""
    return repo.tags()
