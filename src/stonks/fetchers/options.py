"""Fetcher de cadenas de opciones (yfinance): foto diaria → deriv.

yfinance solo da la cadena actual; el histórico se acumula capturando una
foto por día. Por volumen, se limita a las empresas más líquidas y a los
vencimientos más cercanos. Cada atributo se envuelve en try/except.
"""

from datetime import date

import pandas as pd
import yfinance as yf
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.deriv import OptionSnapshot


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v):
    n = _num(v)
    return int(n) if n is not None else None


class OptionsFetcher(BaseFetcher):
    """Captura la foto diaria de cadenas de opciones."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "deriv"
    RATE_LIMIT = 0.5
    N_EXPIRIES = 4  # vencimientos más cercanos
    TOP = 150  # empresas más líquidas por market cap

    def fetch_batch(
        self, tickers: list[str] | None = None, top: int | None = None
    ) -> dict:
        """Capturar cadenas para varios tickers (o el top por market cap)."""
        pares = self._targets(tickers, top or self.TOP)
        hoy = date.today()
        stats = {"empresas": 0, "con_datos": 0, "contratos": 0}
        for i, (ticker, cid) in enumerate(pares, 1):
            self._rate_limit()
            stats["empresas"] += 1
            n = self._fetch_one(ticker, cid, hoy)
            if n:
                stats["con_datos"] += 1
                stats["contratos"] += n
            if i % 25 == 0:
                logger.info("Opciones %d/%d", i, len(pares))
        logger.info(
            "Opciones: %d empresas, %d contratos",
            stats["con_datos"],
            stats["contratos"],
        )
        return stats

    def fetch(self, tickers: list[str] | None = None) -> dict:
        return self.fetch_batch(tickers)

    def _fetch_one(self, ticker: str, cid: int, hoy: date) -> int:
        """Capturar las cadenas de un ticker."""
        try:
            t = yf.Ticker(ticker)
            expiries = t.options[: self.N_EXPIRIES]
        except Exception:  # noqa: BLE001
            return 0
        filas: list[dict] = []
        for exp in expiries:
            try:
                ch = t.option_chain(exp)
            except Exception:  # noqa: BLE001
                continue
            exp_d = date.fromisoformat(exp)
            filas += self._rows(ch.calls, cid, hoy, exp_d, "C")
            filas += self._rows(ch.puts, cid, hoy, exp_d, "P")
        return self._upsert(filas)

    @staticmethod
    def _rows(df, cid, hoy, exp, tipo) -> list[dict]:
        if df is None or df.empty:
            return []
        out = []
        for _, r in df.iterrows():
            strike = _num(r.get("strike"))
            if strike is None:
                continue
            out.append(
                {
                    "company_id": cid,
                    "snapshot_date": hoy,
                    "expiry": exp,
                    "option_type": tipo,
                    "strike": strike,
                    "last_price": _num(r.get("lastPrice")),
                    "bid": _num(r.get("bid")),
                    "ask": _num(r.get("ask")),
                    "volume": _int(r.get("volume")),
                    "open_interest": _int(r.get("openInterest")),
                    "implied_vol": _num(r.get("impliedVolatility")),
                }
            )
        return out

    @staticmethod
    def _targets(tickers, top) -> list[tuple[str, int]]:
        session = get_session()
        try:
            if tickers:
                rows = session.execute(
                    text(
                        "SELECT ticker, id FROM equity.company "
                        "WHERE ticker = ANY(:tk)"
                    ),
                    {"tk": [x.upper() for x in tickers]},
                )
            else:
                rows = session.execute(
                    text(
                        "SELECT ticker, id FROM equity.company "
                        "WHERE is_active = true AND market_cap_usd IS NOT NULL "
                        "ORDER BY market_cap_usd DESC LIMIT :n"
                    ),
                    {"n": top},
                )
            return [(r[0], r[1]) for r in rows]
        finally:
            session.close()

    @staticmethod
    def _upsert(filas) -> int:
        if not filas:
            return 0
        dedup = {
            (
                f["company_id"],
                f["snapshot_date"],
                f["expiry"],
                f["option_type"],
                f["strike"],
            ): f
            for f in filas
        }
        rows = list(dedup.values())
        session = get_session()
        try:
            chunk = 4000
            for i in range(0, len(rows), chunk):
                stmt = insert(OptionSnapshot).values(rows[i : i + chunk])
                stmt = stmt.on_conflict_do_update(
                    index_elements=[
                        "company_id",
                        "snapshot_date",
                        "expiry",
                        "option_type",
                        "strike",
                    ],
                    set_={
                        "last_price": stmt.excluded.last_price,
                        "bid": stmt.excluded.bid,
                        "ask": stmt.excluded.ask,
                        "volume": stmt.excluded.volume,
                        "open_interest": stmt.excluded.open_interest,
                        "implied_vol": stmt.excluded.implied_vol,
                    },
                )
                session.execute(stmt)
            session.commit()
            return len(rows)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.warning("Upsert opciones falló: %s", e)
            return 0
        finally:
            session.close()
