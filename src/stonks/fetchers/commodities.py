"""Fetcher de commodities via yfinance."""

from datetime import date

import yfinance as yf
from sqlalchemy import and_

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
import stonks.models  # noqa: F401
from stonks.models.commodity import (
    Commodity,
    CommodityPrice,
)
from stonks.models.meta import DataSource

# Commodities principales con tickers de yfinance
COMMODITIES = [
    # Metales preciosos
    ("GOLD", "Gold", "precious_metal", None,
     "troy_oz", "GC=F"),
    ("SILVER", "Silver", "precious_metal", None,
     "troy_oz", "SI=F"),
    ("PLATINUM", "Platinum", "precious_metal", None,
     "troy_oz", "PL=F"),
    ("PALLADIUM", "Palladium", "precious_metal", None,
     "troy_oz", "PA=F"),
    # Energía
    ("WTI", "Crude Oil WTI", "energy", "oil",
     "barrel", "CL=F"),
    ("BRENT", "Crude Oil Brent", "energy", "oil",
     "barrel", "BZ=F"),
    ("NATGAS", "Natural Gas", "energy", "gas",
     "mmbtu", "NG=F"),
    ("HEATING_OIL", "Heating Oil", "energy", "oil",
     "gallon", "HO=F"),
    # Agricultura
    ("WHEAT", "Wheat", "agriculture", "grains",
     "bushel", "ZW=F"),
    ("CORN", "Corn", "agriculture", "grains",
     "bushel", "ZC=F"),
    ("SOYBEAN", "Soybeans", "agriculture", "grains",
     "bushel", "ZS=F"),
    ("COFFEE", "Coffee", "agriculture", "softs",
     "pound", "KC=F"),
    ("COCOA", "Cocoa", "agriculture", "softs",
     "metric_ton", "CC=F"),
    ("SUGAR", "Sugar #11", "agriculture", "softs",
     "pound", "SB=F"),
    ("COTTON", "Cotton", "agriculture", "softs",
     "pound", "CT=F"),
    # Metales industriales
    ("COPPER", "Copper", "industrial_metal", None,
     "pound", "HG=F"),
    ("ALUMINUM", "Aluminum", "industrial_metal", None,
     "metric_ton", "ALI=F"),
]


class CommodityFetcher(BaseFetcher):
    """Descarga precios de commodities."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "commodity"
    RATE_LIMIT = 0.5

    def seed_commodities(self) -> int:
        """Insertar commodities de referencia."""
        session = get_session()
        count = 0
        try:
            for (code, name, cat, subcat,
                 unit, yticker) in COMMODITIES:
                if session.query(Commodity).filter_by(
                    code=code
                ).first():
                    continue
                session.add(Commodity(
                    code=code,
                    name=name,
                    category=cat,
                    subcategory=subcat,
                    unit=unit,
                    currency_code="USD",
                    yfinance_ticker=yticker,
                ))
                count += 1
            session.commit()
        finally:
            session.close()
        return count

    def fetch_prices(
        self,
        code: str | None = None,
        period: str = "5y",
    ) -> dict[str, int]:
        """Descargar precios de una o todas las
        commodities."""
        run_id = self._start_run(params={
            "code": code, "period": period,
        })
        stats = {
            "fetched": 0, "inserted": 0,
            "updated": 0, "errors": 0,
        }
        session = get_session()

        try:
            src = session.query(DataSource).filter_by(
                name=self.SOURCE_NAME
            ).first()
            src_id = src.id if src else None

            if code:
                commodities = [
                    session.query(Commodity).filter_by(
                        code=code
                    ).first()
                ]
            else:
                commodities = session.query(
                    Commodity
                ).all()

            for comm in commodities:
                if not comm or not comm.yfinance_ticker:
                    continue

                logger.info(
                    "  Descargando %s (%s)...",
                    comm.name, comm.yfinance_ticker,
                )
                try:
                    t = yf.Ticker(comm.yfinance_ticker)
                    df = t.history(period=period)
                except Exception as e:
                    logger.warning(
                        "  Error %s: %s",
                        comm.code, e,
                    )
                    stats["errors"] += 1
                    continue

                if df.empty:
                    continue

                for idx, row in df.iterrows():
                    dt = idx.date()
                    stats["fetched"] += 1

                    exists = session.query(
                        CommodityPrice
                    ).filter(and_(
                        CommodityPrice.commodity_id
                        == comm.id,
                        CommodityPrice.date == dt,
                    )).first()

                    if exists:
                        continue

                    session.add(CommodityPrice(
                        commodity_id=comm.id,
                        date=dt,
                        open=row.get("Open"),
                        high=row.get("High"),
                        low=row.get("Low"),
                        close=row["Close"],
                        volume=int(
                            row.get("Volume", 0)
                        ) or None,
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
            logger.error("Error commodities: %s", e)
            self._finish_run(
                run_id, "failed", **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats
