"""Fetcher para Yahoo Finance via yfinance."""

from datetime import date, datetime
from pathlib import Path

import yaml
import yfinance as yf
from sqlalchemy import and_

from stonks.config import settings
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
# Importar todos los modelos para resolver FKs
import stonks.models  # noqa: F401
from stonks.models.equity import Company, PriceDaily
from stonks.models.meta import DataSource

# S&P500 principales (top 50 por peso)
SP500_TOP = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL",
    "META", "BRK-B", "TSLA", "UNH", "XOM",
    "JNJ", "JPM", "V", "PG", "MA",
    "HD", "CVX", "MRK", "ABBV", "LLY",
    "PEP", "KO", "COST", "AVGO", "WMT",
    "TMO", "MCD", "CSCO", "ACN", "ABT",
    "DHR", "CRM", "ADBE", "NFLX", "CMCSA",
    "TXN", "NEE", "PM", "WFC", "BMY",
    "AMD", "INTC", "ORCL", "UPS", "RTX",
    "QCOM", "AMGN", "HON", "IBM", "CAT",
]

# Europeas principales
EU_TOP = [
    "ASML", "MC.PA", "NVO", "SAP.DE", "SIE.DE",
    "OR.PA", "AZN.L", "SHEL.L", "NESN.SW",
    "ROG.SW", "NOVN.SW", "TTE.PA", "SAN.PA",
    "AIR.PA", "BNP.PA", "DTE.DE", "ALV.DE",
    "SAN.MC", "IBE.MC", "ITX.MC",
]


def load_tickers_from_yaml(
    region: str | None = None,
) -> list[str]:
    """Cargar tickers desde config/companies.yml.

    Args:
        region: Filtro por región (ej: 'europe_large',
            'asia_pacific'). None = todas.
    """
    yml = settings.config_dir / "companies.yml"
    if not yml.exists():
        return SP500_TOP + EU_TOP

    with open(yml, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if region and region in data:
        return data[region]

    # Todas las regiones
    tickers = []
    for key, lst in data.items():
        tickers.extend(lst)
    return tickers


class YFinanceFetcher(BaseFetcher):
    """Descarga precios e info de empresas desde
    Yahoo Finance."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "equity"
    RATE_LIMIT = 0.5

    def fetch_company_info(
        self, ticker: str
    ) -> Company | None:
        """Obtener/actualizar info de una empresa."""
        session = get_session()
        try:
            t = yf.Ticker(ticker)
            info = t.info
            if not info or "symbol" not in info:
                logger.warning(
                    "Sin datos para %s", ticker
                )
                return None

            company = session.query(
                Company
            ).filter_by(ticker=ticker).first()

            if not company:
                company = Company(
                    ticker=ticker,
                    name=info.get(
                        "longName",
                        info.get("shortName", ticker),
                    ),
                    currency_code=info.get(
                        "currency"
                    ),
                    market_cap_usd=info.get(
                        "marketCap"
                    ),
                    shares_outstanding=info.get(
                        "sharesOutstanding"
                    ),
                    website=info.get("website"),
                    description=info.get(
                        "longBusinessSummary"
                    ),
                    employees=info.get(
                        "fullTimeEmployees"
                    ),
                    is_active=True,
                    country_code=self._resolve_country(
                        info.get("country", "")
                    ),
                )
                session.add(company)
            else:
                company.market_cap_usd = info.get(
                    "marketCap"
                )
                company.shares_outstanding = info.get(
                    "sharesOutstanding"
                )
                company.last_updated = datetime.now()

            session.commit()
            result = company.id
            session.close()
            return result
        except Exception as e:
            session.rollback()
            logger.error(
                "Error info %s: %s", ticker, e
            )
            session.close()
            return None

    def fetch_prices(
        self,
        ticker: str,
        period: str = "5y",
        company_id: int | None = None,
    ) -> dict[str, int]:
        """Descargar precios históricos OHLCV.

        Args:
            ticker: Símbolo bursátil
            period: Período (1y, 5y, 10y, max)
            company_id: ID si ya se conoce

        Returns:
            {"fetched": N, "inserted": N, "updated": N}
        """
        run_id = self._start_run(params={
            "ticker": ticker, "period": period,
        })
        stats = {
            "fetched": 0, "inserted": 0,
            "updated": 0, "errors": 0,
        }
        session = get_session()

        try:
            # Obtener source_id
            src = session.query(DataSource).filter_by(
                name=self.SOURCE_NAME
            ).first()
            src_id = src.id if src else None

            # Obtener company_id si no se proporcionó
            if company_id is None:
                comp = session.query(
                    Company
                ).filter_by(ticker=ticker).first()
                if not comp:
                    # Crear empresa primero
                    session.close()
                    company_id = self.fetch_company_info(
                        ticker
                    )
                    session = get_session()
                    if not company_id:
                        self._finish_run(
                            run_id, "failed",
                            error_log={
                                "msg": "No se pudo "
                                "crear empresa"
                            },
                        )
                        session.close()
                        return stats
                else:
                    company_id = comp.id

            # Descargar datos
            t = yf.Ticker(ticker)
            df = t.history(period=period)

            if df.empty:
                logger.warning(
                    "Sin precios para %s", ticker
                )
                self._finish_run(
                    run_id, "success", **stats
                )
                session.close()
                return stats

            for idx, row in df.iterrows():
                dt = idx.date()
                stats["fetched"] += 1

                existing = session.query(
                    PriceDaily
                ).filter(and_(
                    PriceDaily.company_id
                    == company_id,
                    PriceDaily.date == dt,
                )).first()

                if existing:
                    if float(existing.close) != float(
                        row["Close"]
                    ):
                        existing.open = row.get("Open")
                        existing.high = row.get("High")
                        existing.low = row.get("Low")
                        existing.close = row["Close"]
                        existing.volume = row.get(
                            "Volume"
                        )
                        stats["updated"] += 1
                else:
                    session.add(PriceDaily(
                        company_id=company_id,
                        date=dt,
                        open=row.get("Open"),
                        high=row.get("High"),
                        low=row.get("Low"),
                        close=row["Close"],
                        volume=int(
                            row.get("Volume", 0)
                        ),
                        source_id=src_id,
                    ))
                    stats["inserted"] += 1

            session.commit()
            self._finish_run(
                run_id, "success", **stats
            )

        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error(
                "Error precios %s: %s", ticker, e
            )
            self._finish_run(
                run_id, "failed", **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats

    def fetch_batch(
        self,
        tickers: list[str] | None = None,
        period: str = "5y",
    ) -> dict[str, dict]:
        """Descargar precios para múltiples tickers."""
        if tickers is None:
            tickers = SP500_TOP

        results = {}
        total = len(tickers)
        for i, ticker in enumerate(tickers, 1):
            logger.info(
                "[%d/%d] Descargando %s...",
                i, total, ticker,
            )
            # Primero info de la empresa
            company_id = self.fetch_company_info(
                ticker
            )
            # Luego precios
            results[ticker] = self.fetch_prices(
                ticker,
                period=period,
                company_id=company_id,
            )
            ins = results[ticker]["inserted"]
            upd = results[ticker]["updated"]
            logger.info(
                "  → %s: %d insertados, %d "
                "actualizados",
                ticker, ins, upd,
            )

        return results

    @staticmethod
    def _resolve_country(
        country_name: str,
    ) -> str | None:
        """Convertir nombre de país a ISO alpha-3."""
        import pycountry
        if not country_name:
            return None
        try:
            c = pycountry.countries.lookup(
                country_name
            )
            return c.alpha_3
        except LookupError:
            return None
