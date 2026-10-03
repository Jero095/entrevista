"""
CLI del ETL.

    python -m etl validate --input data/raw/alarms.csv   # limpia y reporta, sin base de datos
    python -m etl init-db                                 # crea la BD y el esquema
    python -m etl load --input data/raw/alarms.csv        # limpia y carga en SQL Server
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from etl.catalog import Catalog, load_catalog
from etl.pipeline import TransformResult, TransformStats, read_source_csv, transform

log = logging.getLogger("etl")

DEFAULT_CATALOG = Path("config/alarm_catalog.csv")


def _merge_stats(total: TransformStats, chunk: TransformStats) -> None:
    for name, value in vars(chunk).items():
        if name == "motivos_rechazo":
            total.motivos_rechazo.update(value)
        else:
            setattr(total, name, getattr(total, name) + value)


def _transform_chunks(path: Path, catalog: Catalog, chunksize: int) -> Iterator[TransformResult]:
    """Procesa el archivo por bloques: la memoria no crece con el tamaño del archivo."""
    for chunk in read_source_csv(path, chunksize=chunksize):
        yield transform(chunk, catalog)


def _report(stats: TransformStats) -> None:
    log.info("Filas leídas:        %d", stats.leidas)
    log.info("Duplicadas:          %d", stats.duplicadas)
    log.info("Válidas:             %d", stats.validas)
    log.info("Rechazadas:          %d", stats.rechazadas)
    for motivo, count in stats.motivos_rechazo.most_common():
        log.info("    %-55s %d", motivo, count)
    log.info("Correcciones: criticidad inferida=%d, tipo inferido=%d, valor BAD=%d, valor vacío=%d",
             stats.criticidad_inferida, stats.tipo_alarma_inferido, stats.valor_bad_quality, stats.valor_vacio)
    if stats.incoherencias_limite or stats.incoherencias_unidad:
        log.warning("El CSV contradice al catálogo (se usó el catálogo): límite=%d, unidad=%d",
                    stats.incoherencias_limite, stats.incoherencias_unidad)


def cmd_validate(args: argparse.Namespace) -> None:
    catalog = load_catalog(args.catalog)
    total = TransformStats()
    rejected: list[pd.DataFrame] = []
    for result in _transform_chunks(args.input, catalog, args.chunksize):
        _merge_stats(total, result.stats)
        rejected.append(result.rejected)
    _report(total)

    if args.rejected_output:
        args.rejected_output.parent.mkdir(parents=True, exist_ok=True)
        pd.concat(rejected).to_csv(args.rejected_output, index=False, encoding="utf-8")
        log.info("Filas rechazadas escritas en %s", args.rejected_output)


def cmd_init_db(args: argparse.Namespace) -> None:
    from etl.loader import init_database
    from etl.settings import DbSettings

    try:
        api_settings = DbSettings.for_api()
    except RuntimeError:
        api_settings = None
    init_database(DbSettings.from_env(), api_settings)


def cmd_load(args: argparse.Namespace) -> None:
    from etl.loader import LoadSession, connect, seed_catalog
    from etl.settings import DbSettings

    catalog = load_catalog(args.catalog)
    settings = DbSettings.from_env()

    with connect(settings) as conn:
        seed_catalog(conn, catalog)
        conn.commit()

        session = LoadSession(conn, archivo=args.input.name)
        total = TransformStats()
        try:
            for result in _transform_chunks(args.input, catalog, args.chunksize):
                _merge_stats(total, result.stats)
                session.load_events(result.valid)
                session.load_rejected(result.rejected)
            session.finish(total)
        except Exception as exc:
            session.fail(exc)
            raise

    _report(total)
    log.info("Lote %d: %d eventos cargados, %d ya existían en la BD",
             session.lote_id, session.cargadas, session.ya_cargadas)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    parser = argparse.ArgumentParser(prog="python -m etl", description="ETL de alarmas SCADA")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_source_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--input", type=Path, default=Path("data/raw/alarms.csv"))
        p.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
        p.add_argument("--chunksize", type=int, default=50_000, help="Filas por bloque procesado")

    p_validate = sub.add_parser("validate", help="Limpia el CSV y reporta la calidad, sin base de datos")
    add_source_args(p_validate)
    p_validate.add_argument("--rejected-output", type=Path, help="CSV donde guardar las filas rechazadas")
    p_validate.set_defaults(func=cmd_validate)

    p_init = sub.add_parser("init-db", help="Crea la base de datos y el esquema (idempotente)")
    p_init.set_defaults(func=cmd_init_db)

    p_load = sub.add_parser("load", help="Limpia el CSV y lo carga en SQL Server")
    add_source_args(p_load)
    p_load.set_defaults(func=cmd_load)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
