#!/usr/bin/env python3
"""Reclasifica empresas US por exchange real via yfinance.

Todas las empresas sin sufijo de ticker están en NASDAQ (id=2)
pero muchas son realmente NYSE, AMEX o NYSE Arca.
Este script consulta yf.Ticker.info["exchange"] y actualiza
equity.company.exchange_id.

Uso:
    python scripts/fix_exchange_mapping.py [--dry-run] [--batch N]
"""

import argparse
import time

import yfinance as yf
from sqlalchemy import text

from stonks.db import engine
from stonks.logger import get_logger

log = get_logger("stonks.fix_exchange")

# yfinance exchange → ref.exchange.id
# Obtenidos de: SELECT id, mic, short_name FROM ref.exchange
YF_EXCHANGE_MAP = {
    "NMS": 2,  # NASDAQ Global Select → NASDAQ
    "NGM": 2,  # NASDAQ Global Market → NASDAQ
    "NCM": 2,  # NASDAQ Capital Market → NASDAQ
    "NYQ": 1,  # NYSE → NYSE
    "PCX": 1,  # NYSE Arca → NYSE (mismo exchange)
    "ASE": 1,  # NYSE American (AMEX) → NYSE
}

RATE_LIMIT = 0.15  # segundos entre requests


def fix_exchanges(
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict:
    """Reclasificar empresas US por exchange real."""
    stats = {
        "total": 0,
        "reclasificadas": 0,
        "errores": 0,
        "sin_cambio": 0,
        "sin_info": 0,
    }

    # Solo empresas US (sin sufijo = exchange_id 2/NASDAQ)
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
            SELECT id, ticker FROM equity.company
            WHERE exchange_id = 2
              AND ticker NOT LIKE '%.%'
            ORDER BY id
        """)
        ).fetchall()

    stats["total"] = len(rows)
    log.info("Empresas US a verificar: %d", stats["total"])

    cambios = []  # (company_id, nuevo_exchange_id)

    for i, (cid, ticker) in enumerate(rows, 1):
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            yf_exchange = info.get("exchange", "")

            new_eid = YF_EXCHANGE_MAP.get(yf_exchange)

            if new_eid is None:
                stats["sin_info"] += 1
                log.warning(
                    "[%d/%d] %s: exchange desconocido '%s'",
                    i,
                    stats["total"],
                    ticker,
                    yf_exchange,
                )
                continue

            if new_eid != 2:
                cambios.append((cid, new_eid))
                stats["reclasificadas"] += 1
                log.info(
                    "[%d/%d] %s: NASDAQ → %s (yf=%s)",
                    i,
                    stats["total"],
                    ticker,
                    "NYSE" if new_eid == 1 else str(new_eid),
                    yf_exchange,
                )
            else:
                stats["sin_cambio"] += 1

            if i % 100 == 0:
                log.info(
                    "Progreso: %d/%d — %d reclasificadas",
                    i,
                    stats["total"],
                    stats["reclasificadas"],
                )

        except Exception as e:
            stats["errores"] += 1
            log.error(
                "[%d/%d] %s: error — %s",
                i,
                stats["total"],
                ticker,
                e,
            )

        time.sleep(RATE_LIMIT)

    # Aplicar cambios en lotes
    if cambios and not dry_run:
        log.info(
            "Aplicando %d cambios en BD...",
            len(cambios),
        )
        with engine.begin() as conn:
            for j in range(0, len(cambios), batch_size):
                lote = cambios[j : j + batch_size]
                for cid, new_eid in lote:
                    conn.execute(
                        text(
                            "UPDATE equity.company "
                            "SET exchange_id = :eid "
                            "WHERE id = :cid"
                        ),
                        {"eid": new_eid, "cid": cid},
                    )
                log.info(
                    "  Lote %d-%d aplicado",
                    j + 1,
                    min(j + batch_size, len(cambios)),
                )
        log.info("Cambios aplicados.")
    elif cambios and dry_run:
        log.info(
            "[DRY-RUN] Se reclasificarían %d empresas",
            len(cambios),
        )

    log.info(
        "Resumen: total=%d, reclasificadas=%d, "
        "sin_cambio=%d, sin_info=%d, errores=%d",
        stats["total"],
        stats["reclasificadas"],
        stats["sin_cambio"],
        stats["sin_info"],
        stats["errores"],
    )
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Fix exchange mapping para empresas US"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar cambios, no aplicar",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=100,
        help="Tamaño de lote para UPDATE (default: 100)",
    )
    args = parser.parse_args()
    fix_exchanges(dry_run=args.dry_run, batch_size=args.batch)


if __name__ == "__main__":
    main()
