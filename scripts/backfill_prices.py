"""Descargar precios para empresas que existen en
equity.company pero no tienen datos en price_daily.
También re-descarga las que tienen <10 años de
histórico.

    python scripts/backfill_prices.py [--period max]
"""

import argparse

from sqlalchemy import text

from stonks.db import get_session
from stonks.fetchers.yfinance_ import YFinanceFetcher
from stonks.logger import setup_logger
from stonks.models.equity import Company

logger = setup_logger("stonks.backfill")


def get_missing_tickers() -> list[str]:
    """Empresas activas sin precios."""
    session = get_session()
    result = session.execute(
        text("""
        SELECT c.ticker
        FROM equity.company c
        WHERE c.is_active = true
          AND NOT EXISTS (
            SELECT 1
            FROM equity.price_daily pd
            WHERE pd.company_id = c.id
          )
        ORDER BY c.ticker
    """)
    )
    tickers = [r[0] for r in result]
    session.close()
    return tickers


def get_short_history_tickers(
    min_years: int = 10,
) -> list[str]:
    """Empresas con menos de min_years de datos."""
    session = get_session()
    result = session.execute(
        text(f"""
        SELECT c.ticker
        FROM equity.company c
        JOIN (
            SELECT company_id,
              MIN(date) as min_d, MAX(date) as max_d
            FROM equity.price_daily
            GROUP BY company_id
        ) r ON r.company_id = c.id
        WHERE c.is_active = true
          AND date_part('year',
            age(r.max_d, r.min_d)) < {min_years}
        ORDER BY c.ticker
    """)
    )
    tickers = [r[0] for r in result]
    session.close()
    return tickers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--period",
        default="max",
        help="Periodo yfinance (max, 10y, 5y...)",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Solo empresas sin precios",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
    )
    args = parser.parse_args()

    missing = get_missing_tickers()
    logger.info("Empresas sin precios: %d", len(missing))

    if args.only_missing:
        tickers = missing
    else:
        short = get_short_history_tickers()
        logger.info("Empresas con <10 años: %d", len(short))
        tickers = list(dict.fromkeys(missing + short))

    if not tickers:
        logger.info("Nada que descargar")
        return

    logger.info(
        "Total a descargar: %d (period=%s)",
        len(tickers),
        args.period,
    )

    fetcher = YFinanceFetcher()
    total = len(tickers)
    success = 0
    errors = 0

    for i, ticker in enumerate(tickers, 1):
        if i % 50 == 1 or i == total:
            logger.info("[%d/%d] %s...", i, total, ticker)
        try:
            session = get_session()
            company = session.query(Company).filter_by(ticker=ticker).first()
            session.close()

            if company:
                fetcher.fetch_prices(
                    ticker,
                    period=args.period,
                    company_id=company.id,
                )
                success += 1
            else:
                cid = fetcher.fetch_company_info(ticker)
                if cid:
                    fetcher.fetch_prices(
                        ticker,
                        period=args.period,
                        company_id=cid,
                    )
                    success += 1
                else:
                    errors += 1
        except Exception as e:
            logger.error("  Error %s: %s", ticker, e)
            errors += 1

        if i % args.batch_size == 0:
            logger.info(
                "--- %d/%d (ok=%d, err=%d) ---",
                i,
                total,
                success,
                errors,
            )

    logger.info(
        "=== Backfill: %d ok, %d err de %d ===",
        success,
        errors,
        total,
    )


if __name__ == "__main__":
    main()
