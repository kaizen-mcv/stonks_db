"""Gestión de particiones mensuales para tablas
intraday."""

import logging
from datetime import date, timedelta

from sqlalchemy import text

log = logging.getLogger("stonks.partitions")

INTRADAY_TABLES = [
    "equity.price_intraday",
    "crypto.price_intraday",
    "forex.rate_intraday",
    "commodity.price_intraday",
]

RETENTION = {
    "1m": 30,  # días
    "5m": 180,  # 6 meses
    "1h": 1095,  # 3 años
}


def ensure_partitions(
    engine,
    months_ahead: int = 3,
    months_back: int = 36,
    tables: list[str] | None = None,
) -> list[str]:
    """Crear particiones mensuales para los próximos N
    meses y los últimos M meses si no existen.

    Returns:
        Lista de particiones creadas.
    """
    if tables is None:
        tables = INTRADAY_TABLES

    created = []
    today = date.today()

    with engine.begin() as conn:
        for table in tables:
            schema, name = table.split(".")
            for offset in range(-months_back, months_ahead + 1):
                y = today.year + (today.month + offset - 1) // 12
                m = (today.month + offset - 1) % 12 + 1
                part_name = f"{name}_{y}_{m:02d}"
                fqn = f"{schema}.{part_name}"

                start = date(y, m, 1)
                if m == 12:
                    end = date(y + 1, 1, 1)
                else:
                    end = date(y, m + 1, 1)

                exists = conn.execute(
                    text(
                        "SELECT 1 FROM pg_class c "
                        "JOIN pg_namespace n ON "
                        "  n.oid = c.relnamespace "
                        "WHERE n.nspname = :schema "
                        "  AND c.relname = :name"
                    ),
                    {"schema": schema, "name": part_name},
                ).scalar()

                if exists:
                    continue

                sql = (
                    f"CREATE TABLE {fqn} PARTITION OF "
                    f"{table} FOR VALUES FROM "
                    f"('{start}') TO ('{end}')"
                )
                conn.execute(text(sql))
                created.append(fqn)
                log.info("Partición creada: %s", fqn)

    return created


def cleanup_intraday(
    engine,
    tables: list[str] | None = None,
) -> dict[str, int]:
    """Eliminar datos intraday que exceden la retención.

    Returns:
        {"deleted_1m": N, "deleted_5m": N, ...}
    """
    if tables is None:
        tables = INTRADAY_TABLES

    stats = {}
    today = date.today()

    with engine.begin() as conn:
        for table in tables:
            for interval, days in RETENTION.items():
                cutoff = today - timedelta(days=days)
                result = conn.execute(
                    text(
                        f"DELETE FROM {table} "
                        f"WHERE interval = :interval "
                        f"AND ts < :cutoff"
                    ),
                    {"interval": interval, "cutoff": cutoff},
                )
                key = f"deleted_{interval}"
                stats[key] = stats.get(key, 0) + result.rowcount
                if result.rowcount > 0:
                    log.info(
                        "%s: %d filas %s borradas (antes de %s)",
                        table,
                        result.rowcount,
                        interval,
                        cutoff,
                    )

    return stats


def drop_empty_partitions(
    engine,
    tables: list[str] | None = None,
) -> list[str]:
    """Eliminar particiones vacías antiguas."""
    if tables is None:
        tables = INTRADAY_TABLES

    dropped = []

    with engine.begin() as conn:
        for table in tables:
            schema, name = table.split(".")
            parts = conn.execute(
                text(
                    "SELECT c.relname FROM pg_inherits i "
                    "JOIN pg_class c ON c.oid = i.inhrelid "
                    "JOIN pg_class p ON p.oid = i.inhparent "
                    "JOIN pg_namespace n ON "
                    "  n.oid = p.relnamespace "
                    "WHERE n.nspname = :schema "
                    "  AND p.relname = :name "
                    "ORDER BY c.relname"
                ),
                {"schema": schema, "name": name},
            ).fetchall()

            for (part_name,) in parts:
                fqn = f"{schema}.{part_name}"
                count = conn.execute(
                    text(f"SELECT count(*) FROM {fqn}")
                ).scalar()
                if count == 0:
                    conn.execute(text(f"DROP TABLE {fqn}"))
                    dropped.append(fqn)
                    log.info(
                        "Partición vacía eliminada: %s",
                        fqn,
                    )

    return dropped
