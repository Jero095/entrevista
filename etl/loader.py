"""
Carga a SQL Server.

Estrategia de carga masiva (evita insertar fila a fila):
1. Los eventos limpios se envían en bloque a una tabla temporal (#stg_evento)
   con `fast_executemany`: pyodbc empaqueta miles de filas por ida y vuelta
   al servidor en lugar de una por fila.
2. Un único INSERT ... SELECT pasa de staging a evento_alarma resolviendo en el
   servidor las claves foráneas (tag -> alarma -> versión de configuración
   vigente en la fecha del evento). Es una operación por conjuntos, no un bucle.
3. La carga es idempotente: los eventos cuyo id_evento_origen ya existe se
   omiten, así que re-ejecutar el ETL sobre el mismo archivo no duplica datos.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyodbc

from etl.catalog import Catalog
from etl.pipeline import TransformStats
from etl.settings import DbSettings

log = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
_GO_SEPARATOR = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)
_MAX_FILA_ORIGINAL = 2000  # tamaño de evento_rechazado.fila_original


def _to_db_datetime(value: datetime | None) -> datetime | None:
    """SQL Server DATETIME2 no guarda zona horaria: se almacena UTC sin tzinfo."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _none_if_na(value):
    """pandas representa los nulos como NaN (incluso en columnas de texto); el driver espera None."""
    return None if pd.isna(value) else value


def connect(settings: DbSettings, database: str | None = None, autocommit: bool = False) -> pyodbc.Connection:
    return pyodbc.connect(settings.connection_string(database), autocommit=autocommit)


def run_sql_script(conn: pyodbc.Connection, path: Path) -> None:
    """Ejecuta un script T-SQL separado por 'GO' (separador del cliente, no del servidor)."""
    script = path.read_text(encoding="utf-8")
    cursor = conn.cursor()
    for batch in _GO_SEPARATOR.split(script):
        if batch.strip():
            cursor.execute(batch)
    conn.commit()


# Usuario de solo lectura para la API (principio de mínimo privilegio): solo puede
# hacer SELECT sobre las dos vistas que expone la API, nunca escribir ni leer tablas.
# CREATE LOGIN no acepta parámetros, así que el SQL dinámico se arma en el servidor
# con QUOTENAME a partir de parámetros: ni el nombre ni la contraseña se concatenan
# en Python, lo que evita inyección SQL aunque vengan de variables de entorno.
_API_USER_SQL = """
DECLARE @usuario sysname = ?, @password nvarchar(128) = ?, @sql nvarchar(max);

IF SUSER_ID(@usuario) IS NULL
    SET @sql = N'CREATE LOGIN ' + QUOTENAME(@usuario) + N' WITH PASSWORD = ' + QUOTENAME(@password, '''')
             + N', DEFAULT_DATABASE = ' + QUOTENAME(DB_NAME());
ELSE
    SET @sql = N'ALTER LOGIN ' + QUOTENAME(@usuario) + N' WITH PASSWORD = ' + QUOTENAME(@password, '''');
EXEC (@sql);

IF USER_ID(@usuario) IS NULL
BEGIN
    SET @sql = N'CREATE USER ' + QUOTENAME(@usuario) + N' FOR LOGIN ' + QUOTENAME(@usuario);
    EXEC (@sql);
END

SET @sql = N'GRANT SELECT ON dbo.v_evento_alarma TO ' + QUOTENAME(@usuario)
         + N'; GRANT SELECT ON dbo.v_catalogo TO ' + QUOTENAME(@usuario);
EXEC (@sql);
"""


def create_api_user(conn: pyodbc.Connection, user: str, password: str) -> None:
    conn.cursor().execute(_API_USER_SQL, user, password)
    conn.commit()
    log.info("Usuario de solo lectura '%s' listo para la API", user)


def init_database(settings: DbSettings, api_settings: DbSettings | None = None) -> None:
    # CREATE DATABASE no puede ejecutarse dentro de una transacción.
    with connect(settings, database="master", autocommit=True) as conn:
        run_sql_script(conn, SQL_DIR / "00_create_database.sql")
    with connect(settings) as conn:
        run_sql_script(conn, SQL_DIR / "01_schema.sql")
        if api_settings:
            create_api_user(conn, api_settings.user, api_settings.password)
        else:
            log.warning("DB_API_PASSWORD no definida: no se crea el usuario de solo lectura de la API")
    log.info("Base de datos '%s' y esquema listos", settings.database)


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #

_SEED_CATALOG_SQL = """
INSERT INTO dbo.area (nombre)
SELECT DISTINCT c.area FROM #catalogo c
WHERE NOT EXISTS (SELECT 1 FROM dbo.area a WHERE a.nombre = c.area);

-- Atributos del instrumento: se toman de la versión más reciente del catálogo.
MERGE dbo.tag AS d
USING (
    SELECT x.tag, x.descripcion, x.unidad, a.id AS area_id
    FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY tag ORDER BY vigente_desde DESC) AS rn
          FROM #catalogo) x
    JOIN dbo.area a ON a.nombre = x.area
    WHERE x.rn = 1
) AS s
ON d.codigo = s.tag
WHEN MATCHED THEN UPDATE SET descripcion = s.descripcion, unidad = s.unidad, area_id = s.area_id
WHEN NOT MATCHED THEN INSERT (codigo, descripcion, unidad, area_id)
                      VALUES (s.tag, s.descripcion, s.unidad, s.area_id);

INSERT INTO dbo.alarma (tag_id, tipo_alarma)
SELECT DISTINCT t.id, c.tipo_alarma
FROM #catalogo c JOIN dbo.tag t ON t.codigo = c.tag
WHERE NOT EXISTS (SELECT 1 FROM dbo.alarma a WHERE a.tag_id = t.id AND a.tipo_alarma = c.tipo_alarma);
"""

_CATALOG_VERSIONS_SQL = """
SELECT a.id AS alarma_id, c.limite, cr.id AS criticidad_id, c.vigente_desde, c.vigente_hasta, c.tag, c.tipo_alarma
FROM #catalogo c
JOIN dbo.tag t        ON t.codigo = c.tag
JOIN dbo.alarma a     ON a.tag_id = t.id AND a.tipo_alarma = c.tipo_alarma
JOIN dbo.criticidad cr ON cr.nombre = c.criticidad
"""

_CHANGED_VERSIONS_SQL = f"""
SELECT s.tag, s.tipo_alarma, s.vigente_desde
FROM ({_CATALOG_VERSIONS_SQL}) s
JOIN dbo.alarma_config d ON d.alarma_id = s.alarma_id AND d.vigente_desde = s.vigente_desde
WHERE d.limite <> s.limite OR d.criticidad_id <> s.criticidad_id
"""

_MERGE_VERSIONS_SQL = f"""
MERGE dbo.alarma_config AS d
USING ({_CATALOG_VERSIONS_SQL}) AS s
ON d.alarma_id = s.alarma_id AND d.vigente_desde = s.vigente_desde
-- Única modificación permitida sobre una versión existente: cerrarla cuando aparece una más nueva.
WHEN MATCHED AND d.vigente_hasta IS NULL AND s.vigente_hasta IS NOT NULL
    THEN UPDATE SET vigente_hasta = s.vigente_hasta
WHEN NOT MATCHED
    THEN INSERT (alarma_id, limite, criticidad_id, vigente_desde, vigente_hasta)
         VALUES (s.alarma_id, s.limite, s.criticidad_id, s.vigente_desde, s.vigente_hasta);
"""


def seed_catalog(conn: pyodbc.Connection, catalog: Catalog) -> None:
    """Sincroniza el catálogo del archivo con la BD (idempotente)."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE #catalogo (
            tag VARCHAR(20), descripcion NVARCHAR(200), area NVARCHAR(50), unidad NVARCHAR(20) NULL,
            tipo_alarma VARCHAR(5), limite DECIMAL(18, 4), criticidad VARCHAR(10),
            vigente_desde DATETIME2(0), vigente_hasta DATETIME2(0) NULL
        )""")
    cursor.executemany(
        "INSERT INTO #catalogo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (a.tag, a.descripcion, a.area, a.unidad, a.tipo_alarma, a.limite, a.criticidad,
             _to_db_datetime(a.vigente_desde), _to_db_datetime(hasta))
            for a, hasta in catalog.versions()
        ],
    )
    cursor.execute(_SEED_CATALOG_SQL)

    # Las versiones son inmutables: cambiar un límite exige agregar una versión nueva
    # al catálogo, no editar una existente (si no, el histórico se reinterpretaría).
    changed = cursor.execute(_CHANGED_VERSIONS_SQL).fetchall()
    if changed:
        detalle = ", ".join(f"{r.tag} {r.tipo_alarma} desde {r.vigente_desde:%Y-%m-%d}" for r in changed)
        raise ValueError(
            "El catálogo modifica versiones ya cargadas (límite o criticidad). "
            f"Agregue una versión nueva con otra fecha en lugar de editarla: {detalle}"
        )

    cursor.execute(_MERGE_VERSIONS_SQL)
    cursor.execute("DROP TABLE #catalogo")
    log.info("Catálogo sincronizado: %d versiones de alarma", len(catalog.versions()))


# --------------------------------------------------------------------------- #
# Eventos
# --------------------------------------------------------------------------- #

_CREATE_STAGING_SQL = """
CREATE TABLE #stg_evento (
    id_evento_origen BIGINT       NOT NULL PRIMARY KEY,
    tag              VARCHAR(20)  NOT NULL,
    tipo_alarma      VARCHAR(5)   NOT NULL,
    timestamp_utc    DATETIME2(3) NOT NULL,
    estado           VARCHAR(6)   NOT NULL,
    criticidad       VARCHAR(10)  NOT NULL,
    valor            FLOAT        NULL,
    calidad_valor    VARCHAR(4)   NULL
)"""

_COUNT_ALREADY_LOADED_SQL = """
SELECT COUNT(*) FROM #stg_evento s
WHERE EXISTS (SELECT 1 FROM dbo.evento_alarma e WHERE e.id_evento_origen = s.id_evento_origen)
"""

_INSERT_EVENTS_SQL = """
INSERT INTO dbo.evento_alarma
    (id_evento_origen, alarma_config_id, timestamp_utc, estado, criticidad_id, valor, calidad_valor, lote_id)
SELECT s.id_evento_origen, ac.id, s.timestamp_utc, s.estado, c.id, s.valor, s.calidad_valor, ?
FROM #stg_evento s
JOIN dbo.tag t            ON t.codigo = s.tag
JOIN dbo.alarma a         ON a.tag_id = t.id AND a.tipo_alarma = s.tipo_alarma
-- Versión de configuración vigente cuando ocurrió el evento
JOIN dbo.alarma_config ac ON ac.alarma_id = a.id
                         AND s.timestamp_utc >= ac.vigente_desde
                         AND (ac.vigente_hasta IS NULL OR s.timestamp_utc < ac.vigente_hasta)
JOIN dbo.criticidad c     ON c.nombre = s.criticidad
WHERE NOT EXISTS (SELECT 1 FROM dbo.evento_alarma e WHERE e.id_evento_origen = s.id_evento_origen)
ORDER BY s.timestamp_utc   -- inserta en el orden del índice clustered
"""


def event_rows(valid: pd.DataFrame) -> list[tuple]:
    """Convierte los eventos limpios en tuplas con tipos nativos para el driver (orden de #stg_evento)."""
    return [
        (int(r.id_evento_origen), r.tag, r.tipo_alarma, _to_db_datetime(r.timestamp_utc),
         r.estado, r.criticidad, _none_if_na(r.valor), _none_if_na(r.calidad_valor))
        for r in valid.itertuples(index=False)
    ]


class LoadSession:
    """Una ejecución del ETL = un lote_carga. Todo el lote se confirma o se revierte junto."""

    def __init__(self, conn: pyodbc.Connection, archivo: str):
        self.conn = conn
        self.cursor = conn.cursor()
        self.cursor.fast_executemany = True
        self.ya_cargadas = 0
        self.cargadas = 0
        # El lote se registra y confirma aparte para que quede constancia aunque la carga falle.
        self.lote_id = self.cursor.execute(
            "INSERT INTO dbo.lote_carga (archivo) OUTPUT INSERTED.id VALUES (?)", archivo
        ).fetchval()
        self.conn.commit()

    def load_events(self, valid: pd.DataFrame) -> None:
        if valid.empty:
            return
        rows = event_rows(valid)
        self.cursor.execute(_CREATE_STAGING_SQL)
        # Tipos explícitos: con fast_executemany, pyodbc los deduce de la primera fila
        # si no se declaran, y falla cuando esa fila trae un NULL.
        self.cursor.setinputsizes([
            (pyodbc.SQL_BIGINT, 0, 0), (pyodbc.SQL_VARCHAR, 20, 0), (pyodbc.SQL_VARCHAR, 5, 0),
            (pyodbc.SQL_TYPE_TIMESTAMP, 23, 3), (pyodbc.SQL_VARCHAR, 6, 0), (pyodbc.SQL_VARCHAR, 10, 0),
            (pyodbc.SQL_DOUBLE, 0, 0), (pyodbc.SQL_VARCHAR, 4, 0),
        ])
        self.cursor.executemany("INSERT INTO #stg_evento VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        self.cursor.setinputsizes(None)

        ya_cargadas = self.cursor.execute(_COUNT_ALREADY_LOADED_SQL).fetchval()
        cargadas = self.cursor.execute(_INSERT_EVENTS_SQL, self.lote_id).rowcount
        sin_config = len(rows) - ya_cargadas - cargadas
        self.cursor.execute("DROP TABLE #stg_evento")

        if sin_config:
            # El pipeline ya validó contra el mismo catálogo que se acaba de sincronizar,
            # así que esto indica un catálogo de BD inconsistente: mejor abortar que cargar a medias.
            raise RuntimeError(f"{sin_config} eventos no encontraron configuración de alarma en la BD")

        self.ya_cargadas += ya_cargadas
        self.cargadas += cargadas

    def load_rejected(self, rejected: pd.DataFrame) -> None:
        if rejected.empty:
            return
        rows = [(self.lote_id, r.fila_original[:_MAX_FILA_ORIGINAL], r.motivo[:500])
                for r in rejected.itertuples(index=False)]
        self.cursor.executemany(
            "INSERT INTO dbo.evento_rechazado (lote_id, fila_original, motivo) VALUES (?, ?, ?)", rows
        )

    def finish(self, stats: TransformStats) -> None:
        self.cursor.execute(
            """UPDATE dbo.lote_carga
               SET fin = SYSUTCDATETIME(), estado = 'OK', filas_leidas = ?, filas_duplicadas = ?,
                   filas_ya_cargadas = ?, filas_cargadas = ?, filas_rechazadas = ?
               WHERE id = ?""",
            stats.leidas, stats.duplicadas, self.ya_cargadas, self.cargadas, stats.rechazadas, self.lote_id,
        )
        self.conn.commit()

    def fail(self, error: Exception) -> None:
        self.conn.rollback()
        self.cursor.execute(
            "UPDATE dbo.lote_carga SET fin = SYSUTCDATETIME(), estado = 'ERROR', mensaje_error = ? WHERE id = ?",
            str(error)[:1000], self.lote_id,
        )
        self.conn.commit()
