"""Fetcher de tipos de cambio desde el ECB."""

from datetime import date, datetime
from xml.etree import ElementTree

import requests
from sqlalchemy import and_

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
import stonks.models  # noqa: F401
from stonks.models.forex import CurrencyPair, ForexRate
from stonks.models.meta import DataSource

# Namespace del XML del ECB
NS = {
    "gesmes": "http://www.gesmes.org/xml/2002-08-01",
    "ecb": "http://www.ecb.int/vocabulary/"
    "2002-08-01/eurofxref",
}

# Pares principales vs EUR
ECB_CURRENCIES = [
    "USD", "JPY", "GBP", "CHF", "AUD", "CAD",
    "SEK", "NOK", "DKK", "HKD", "SGD", "KRW",
    "CNY", "NZD", "TRY", "BRL", "MXN", "ZAR",
    "INR", "PLN", "HUF", "CZK", "ILS", "THB",
    "IDR", "MYR", "PHP", "RON", "BGN", "HRK",
    "ISK", "RUB",
]


class ECBForexFetcher(BaseFetcher):
    """Descarga tipos de cambio diarios del ECB."""

    SOURCE_NAME = "ecb"
    DOMAIN = "forex"
    RATE_LIMIT = 0.5
    # Histórico completo (desde 1999)
    HISTORY_URL = (
        "https://www.ecb.europa.eu/stats/eurofxref/"
        "eurofxref-hist.xml"
    )
    # Últimos 90 días
    RECENT_URL = (
        "https://www.ecb.europa.eu/stats/eurofxref/"
        "eurofxref-hist-90d.xml"
    )

    def _ensure_pairs(
        self, session
    ) -> dict[str, int]:
        """Crear pares EUR/XXX si no existen.
        Solo para divisas que existen en ref.currency.
        """
        from stonks.models.ref import Currency

        # Verificar qué divisas existen
        existing_currencies = {
            c.code for c in
            session.query(Currency.code).all()
        }

        pair_cache: dict[str, int] = {}
        for cur in ECB_CURRENCIES:
            if cur not in existing_currencies:
                continue
            pair_code = f"EUR{cur}"
            pair = session.query(
                CurrencyPair
            ).filter_by(
                pair_code=pair_code
            ).first()
            if not pair:
                pair = CurrencyPair(
                    base_currency="EUR",
                    quote_currency=cur,
                    pair_code=pair_code,
                    category=(
                        "major" if cur in (
                            "USD", "GBP", "JPY",
                            "CHF",
                        ) else "minor"
                    ),
                )
                session.add(pair)
                session.flush()
            pair_cache[cur] = pair.id
        session.commit()
        return pair_cache

    def fetch_rates(
        self, full_history: bool = False
    ) -> dict[str, int]:
        """Descargar tipos de cambio.

        Args:
            full_history: True para todo desde 1999,
                False para últimos 90 días.
        """
        url = (
            self.HISTORY_URL if full_history
            else self.RECENT_URL
        )
        run_id = self._start_run(params={
            "full_history": full_history,
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

            pair_cache = self._ensure_pairs(session)

            # Descargar XML
            logger.info(
                "Descargando XML del ECB (%s)...",
                "completo" if full_history
                else "90 días",
            )
            self._rate_limit()
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()

            root = ElementTree.fromstring(resp.content)

            # Parsear XML
            for cube_time in root.findall(
                ".//ecb:Cube[@time]", NS
            ):
                dt_str = cube_time.get("time")
                dt = date.fromisoformat(dt_str)

                for cube_rate in cube_time.findall(
                    "ecb:Cube[@currency]", NS
                ):
                    currency = cube_rate.get("currency")
                    rate_str = cube_rate.get("rate")

                    if currency not in pair_cache:
                        continue

                    stats["fetched"] += 1
                    pair_id = pair_cache[currency]
                    rate_val = float(rate_str)

                    exists = session.query(
                        ForexRate
                    ).filter(and_(
                        ForexRate.pair_id == pair_id,
                        ForexRate.date == dt,
                    )).first()

                    if exists:
                        continue

                    session.add(ForexRate(
                        pair_id=pair_id,
                        date=dt,
                        close=rate_val,
                        source_id=src_id,
                    ))
                    stats["inserted"] += 1

            session.commit()
            self._finish_run(
                run_id, "success", **stats
            )
            logger.info(
                "ECB Forex: %d insertados",
                stats["inserted"],
            )

        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error ECB forex: %s", e)
            self._finish_run(
                run_id, "failed", **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats
