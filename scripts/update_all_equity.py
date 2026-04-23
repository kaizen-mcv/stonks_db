"""Actualizar precios historicos de todas las empresas
de la BD con period=max."""

from stonks.db import get_session
from stonks.fetchers.yfinance_ import (
    YFinanceFetcher,
    load_tickers_from_yaml,
)
from stonks.logger import get_logger, setup_logger
from stonks.models.equity import Company

setup_logger("stonks.fetch")
logger = get_logger("stonks.update_all")


def main() -> None:
    """Descargar histórico completo de TODAS las
    empresas de equity.company."""
    # Tickers del batch global YAML (ya actualizados
    # hace poco)
    yaml_tickers = set(load_tickers_from_yaml())
    logger.info(
        "Tickers en YAML (ya actualizados): %d",
        len(yaml_tickers),
    )

    # Todas las empresas de la BD
    session = get_session()
    all_companies = (
        session.query(Company.ticker, Company.id)
        .filter(Company.is_active.is_(True))
        .all()
    )
    session.close()

    # Filtrar los que NO estan en el YAML
    pending = [(t, cid) for t, cid in all_companies if t not in yaml_tickers]
    logger.info(
        "Empresas totales: %d",
        len(all_companies),
    )
    logger.info(
        "Empresas pendientes de actualizar: %d",
        len(pending),
    )

    fetcher = YFinanceFetcher()
    total_ins = 0
    total_upd = 0
    errors = 0

    for i, (ticker, cid) in enumerate(pending, 1):
        try:
            logger.info(
                "[%d/%d] %s...",
                i,
                len(pending),
                ticker,
            )
            stats = fetcher.fetch_prices(
                ticker,
                period="max",
                company_id=cid,
            )
            ins = stats["inserted"]
            upd = stats["updated"]
            total_ins += ins
            total_upd += upd
            logger.info(
                "  → %s: %d ins, %d upd",
                ticker,
                ins,
                upd,
            )
        except Exception as e:
            errors += 1
            logger.warning("  Error %s: %s", ticker, e)

    logger.info("")
    logger.info("=== RESUMEN ===")
    logger.info("Total insertados: %d", total_ins)
    logger.info("Total actualizados: %d", total_upd)
    logger.info("Errores: %d", errors)


if __name__ == "__main__":
    main()
