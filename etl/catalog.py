"""
Catálogo de instrumentos y alarmas ("Master Alarm Database" de ISA-18.2).

Es la configuración de la planta: qué tags existen, en qué unidad miden y qué
alarmas tienen configuradas (tipo, límite, criticidad). Vive en un archivo
versionado (config/alarm_catalog.csv) y se carga a la base de datos como seed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from etl.normalizers import CRITICIDADES, TIPOS_ALARMA, normalize_tag


@dataclass(frozen=True)
class AlarmaCatalogo:
    tag: str
    descripcion: str
    area: str
    unidad: str | None
    tipo_alarma: str
    limite: Decimal
    criticidad: str
    vigente_desde: datetime


class Catalog:
    """
    Una alarma (tag + tipo) puede tener varias versiones de configuración. En el
    archivo solo se indica vigente_desde: cada versión es válida hasta que
    empieza la siguiente.
    """

    def __init__(self, alarmas: list[AlarmaCatalogo]):
        self.alarmas = sorted(alarmas, key=lambda a: (a.tag, a.tipo_alarma, a.vigente_desde))
        self._versions: dict[tuple[str, str], list[AlarmaCatalogo]] = {}
        self._tipos_by_tag: dict[str, set[str]] = {}
        for alarma in self.alarmas:
            self._versions.setdefault((alarma.tag, alarma.tipo_alarma), []).append(alarma)
            self._tipos_by_tag.setdefault(alarma.tag, set()).add(alarma.tipo_alarma)

    def has_tag(self, tag: str) -> bool:
        return tag in self._tipos_by_tag

    def resolve_tipo(self, tag: str, tipo_alarma: str | None) -> str | None:
        """
        Devuelve el tipo de alarma a usar para el evento. Si el evento no trae el
        tipo y el tag tiene una única alarma configurada, no hay ambigüedad.
        """
        tipos = self._tipos_by_tag.get(tag, set())
        if tipo_alarma is None:
            return next(iter(tipos)) if len(tipos) == 1 else None
        return tipo_alarma if tipo_alarma in tipos else None

    def version_at(self, tag: str, tipo_alarma: str, at: datetime) -> AlarmaCatalogo | None:
        """Versión de configuración vigente en el instante `at` (UTC)."""
        vigente = None
        for version in self._versions.get((tag, tipo_alarma), []):
            if version.vigente_desde <= at:
                vigente = version
        return vigente

    def versions(self) -> list[tuple[AlarmaCatalogo, datetime | None]]:
        """Todas las versiones con su vigente_hasta calculado (None = vigente)."""
        result = []
        for versiones in self._versions.values():
            hasta = [v.vigente_desde for v in versiones[1:]] + [None]
            result.extend(zip(versiones, hasta))
        return result


def load_catalog(path: Path) -> Catalog:
    """Lee y valida el catálogo. Un catálogo inválido es un error de configuración: falla rápido."""
    alarmas: list[AlarmaCatalogo] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            try:
                alarma = AlarmaCatalogo(
                    tag=normalize_tag(row["tag"]),
                    descripcion=row["descripcion"].strip(),
                    area=row["area"].strip(),
                    unidad=row["unidad"].strip() or None,
                    tipo_alarma=row["tipo_alarma"].strip().upper(),
                    limite=Decimal(row["limite"]),
                    criticidad=row["criticidad"].strip().upper(),
                    # Las fechas del catálogo se expresan en UTC.
                    vigente_desde=datetime.fromisoformat(row["vigente_desde"]).replace(tzinfo=timezone.utc),
                )
            except (KeyError, ValueError, ArithmeticError) as exc:
                raise ValueError(f"{path}:{line_no}: fila de catálogo inválida: {exc}") from exc

            if alarma.tipo_alarma not in TIPOS_ALARMA:
                raise ValueError(f"{path}:{line_no}: tipo_alarma desconocido {alarma.tipo_alarma!r}")
            if alarma.criticidad not in CRITICIDADES:
                raise ValueError(f"{path}:{line_no}: criticidad desconocida {alarma.criticidad!r}")
            alarmas.append(alarma)

    claves = [(a.tag, a.tipo_alarma, a.vigente_desde) for a in alarmas]
    if len(claves) != len(set(claves)):
        raise ValueError(f"{path}: hay versiones de alarma duplicadas (tag, tipo_alarma, vigente_desde)")
    return Catalog(alarmas)
