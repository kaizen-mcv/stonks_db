#!/usr/bin/env python3
"""Limpieza de datos intraday según política de
retención y eliminación de particiones vacías.

Uso:
    python scripts/cleanup_intraday.py [--dry-run]
"""

import argparse

from stonks.db import engine
from stonks.logger import get_logger
from stonks.utils.partitions import (
    cleanup_intraday,
    drop_empty_partitions,
)

log = get_logger("stonks.cleanup")


def main():
    parser = argparse.ArgumentParser(description="Limpieza intraday")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar, no borrar",
    )
    args = parser.parse_args()

    if args.dry_run:
        log.info("[DRY-RUN] No se borrarán datos")
        return

    stats = cleanup_intraday(engine)
    log.info("Cleanup stats: %s", stats)

    dropped = drop_empty_partitions(engine)
    if dropped:
        log.info(
            "Particiones vacías eliminadas: %s",
            dropped,
        )


if __name__ == "__main__":
    main()
