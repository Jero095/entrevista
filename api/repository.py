"""
Acceso a datos. Es el ÚNICO módulo de la API que contiene SQL.

La API lee a través de dos vistas (v_evento_alarma y v_catalogo), no de las
tablas: el usuario de BD de la API solo tiene permiso SELECT sobre ellas, y el
modelo físico puede cambiar sin tocar este código mientras las vistas se mantengan.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pyodbc

from api.schemas import NIVEL, Criticidad, FiltroAlarmas, FiltroResumen, FiltroTiempo, FiltroTopTags

_COLUMNAS_EVENTO = (
    "id, id_evento_origen, timestamp_utc, tag, descripcion, area, tipo_alarma, criticidad, "
    "estado, valor, calidad_valor, unidad, limite, desviacion_limite"
)


def _naive_utc(value: datetime) -> datetime:
    """La BD guarda DATETIME2 en UTC sin zona horaria."""
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _filas(cursor: pyodbc.Cursor) -> list[dict]:
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def _where(f: FiltroTiempo, solo_alarmas: bool = False) -> tuple[str, list]:
    """
    Construye el WHERE a partir de los filtros presentes.

    El texto SQL solo se arma con fragmentos FIJOS escritos aquí; los valores que
    envía el usuario viajan siempre como parámetros '?'. No hay inyección SQL posible.
    """
    clausulas: list[str] = []
    params: list = []

    if f.desde:
        clausulas.append("timestamp_utc >= ?")
        params.append(_naive_utc(f.desde))
    if f.hasta:
        clausulas.append("timestamp_utc < ?")
        params.append(_naive_utc(f.hasta))
    if tag := getattr(f, "tag", None):
        clausulas.append("tag = ?")
        params.append(tag)
    if criticidades := getattr(f, "criticidad", None):
        clausulas.append(f"criticidad IN ({', '.join('?' * len(criticidades))})")
        params.extend(c.value for c in criticidades)
    if criticidad_min := getattr(f, "criticidad_min", None):
        clausulas.append("criticidad_nivel >= ?")
        params.append(NIVEL[criticidad_min])
    if estado := getattr(f, "estado", None):
        clausulas.append("estado = ?")
        params.append(estado.value)
    if solo_alarmas:
        # Cada alarma genera hasta 3 eventos (ACTIVE, ACK, RTN): para contar
        # "veces que saltó" se cuenta solo la activación.
        clausulas.append("estado = 'ACTIVE'")

    return ("WHERE " + " AND ".join(clausulas)) if clausulas else "", params


class AlarmaRepository:
    def __init__(self, conn: pyodbc.Connection):
        self.conn = conn

    def listar(self, f: FiltroAlarmas) -> tuple[list[dict], int]:
        where, params = _where(f)
        cursor = self.conn.cursor()
        total = cursor.execute(f"SELECT COUNT(*) FROM dbo.v_evento_alarma {where}", params).fetchval()
        cursor.execute(
            f"""SELECT {_COLUMNAS_EVENTO}
                FROM dbo.v_evento_alarma {where}
                ORDER BY timestamp_utc DESC, id DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
            [*params, (f.page - 1) * f.size, f.size],
        )
        return _filas(cursor), total

    def obtener(self, id_evento: int) -> dict | None:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT {_COLUMNAS_EVENTO} FROM dbo.v_evento_alarma WHERE id = ?", id_evento)
        filas = _filas(cursor)
        return filas[0] if filas else None

    def existe_tag(self, codigo: str) -> bool:
        cursor = self.conn.cursor()
        return cursor.execute("SELECT TOP 1 1 FROM dbo.v_catalogo WHERE tag = ?", codigo).fetchone() is not None

    def top_tags(self, f: FiltroTopTags) -> list[dict]:
        where, params = _where(f, solo_alarmas=f.contar == "alarmas")
        cursor = self.conn.cursor()
        cursor.execute(
            f"""SELECT TOP (?) tag, descripcion, area, COUNT(*) AS total
                FROM dbo.v_evento_alarma {where}
                GROUP BY tag, descripcion, area
                ORDER BY total DESC, tag""",
            [f.limit, *params],
        )
        return _filas(cursor)

    def por_criticidad(self, f: FiltroResumen) -> list[dict]:
        """Alarmas por criticidad, incluyendo las criticidades sin alarmas (total 0)."""
        where, params = _where(f, solo_alarmas=True)
        cursor = self.conn.cursor()
        cursor.execute(
            f"""SELECT criticidad, COUNT(*) AS total
                FROM dbo.v_evento_alarma {where}
                GROUP BY criticidad""",
            params,
        )
        totales = {fila["criticidad"]: fila["total"] for fila in _filas(cursor)}
        return [
            {"criticidad": c, "nivel": NIVEL[c], "total": totales.get(c.value, 0)}
            for c in sorted(Criticidad, key=NIVEL.get, reverse=True)
        ]

    def tags(self) -> list[dict]:
        """Catálogo con la configuración vigente de cada alarma, agrupado por tag."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT tag, descripcion, area, unidad, tipo_alarma, limite, criticidad, vigente_desde
               FROM dbo.v_catalogo
               ORDER BY tag, tipo_alarma"""
        )
        por_tag: dict[str, dict] = {}
        for fila in _filas(cursor):
            tag = por_tag.setdefault(fila["tag"], {
                "tag": fila["tag"], "descripcion": fila["descripcion"], "area": fila["area"],
                "unidad": fila["unidad"], "alarmas": [],
            })
            tag["alarmas"].append({
                "tipo_alarma": fila["tipo_alarma"], "limite": fila["limite"],
                "criticidad": fila["criticidad"],
                "vigente_desde": fila["vigente_desde"].replace(tzinfo=timezone.utc),
            })
        return list(por_tag.values())

    def ping(self) -> None:
        self.conn.cursor().execute("SELECT 1").fetchval()
