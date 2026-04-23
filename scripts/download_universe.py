"""Descargar precios para todo el universo de
~5000 empresas. Ejecutar con:
    python -m scripts.download_universe [--period 5y]
"""

import argparse
import sys
from pathlib import Path

from stonks.db import get_session
from stonks.fetchers.yfinance_ import YFinanceFetcher
from stonks.logger import setup_logger
from stonks.models.equity import Company

logger = setup_logger("stonks.universe")

DATA_DIR = Path("./data")


def load_tickers() -> list[str]:
    """Cargar tickers del archivo generado."""
    path = DATA_DIR / "universe_tickers.txt"
    if not path.exists():
        logger.error("Ejecuta primero: python scripts/build_universe.py")
        sys.exit(1)
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def get_existing_tickers() -> set[str]:
    """Obtener tickers que ya están en la BD."""
    session = get_session()
    existing = {c.ticker for c in session.query(Company.ticker).all()}
    session.close()
    return existing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--period",
        default="5y",
        help="Período: 1y, 5y, 10y, max",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Saltar empresas ya descargadas",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Guardar progreso cada N empresas",
    )
    args = parser.parse_args()

    all_tickers = load_tickers()
    logger.info(
        "Universo: %d tickers totales",
        len(all_tickers),
    )

    if args.skip_existing:
        existing = get_existing_tickers()
        tickers = [t for t in all_tickers if t not in existing]
        logger.info(
            "Ya descargados: %d, pendientes: %d",
            len(existing),
            len(tickers),
        )
    else:
        tickers = all_tickers

    if not tickers:
        logger.info("Nada que descargar")
        return

    fetcher = YFinanceFetcher()
    total = len(tickers)
    success = 0
    errors = 0

    for i, ticker in enumerate(tickers, 1):
        logger.info("[%d/%d] %s...", i, total, ticker)
        try:
            company_id = fetcher.fetch_company_info(ticker)
            if company_id:
                stats = fetcher.fetch_prices(
                    ticker,
                    period=args.period,
                    company_id=company_id,
                )
                ins = stats["inserted"]
                logger.info("  → %d precios", ins)
                success += 1
            else:
                logger.warning("  → sin datos (ticker inválido?)")
                errors += 1
        except Exception as e:
            logger.error("  → error: %s", e)
            errors += 1

        # Progreso cada batch_size
        if i % args.batch_size == 0:
            logger.info(
                "--- Progreso: %d/%d (ok=%d, err=%d) ---",
                i,
                total,
                success,
                errors,
            )

    logger.info(
        "=== Completado: %d ok, %d errores de %d total ===",
        success,
        errors,
        total,
    )


if __name__ == "__main__":
    main()
