"""Fetcher de forex via yfinance.

Descarga OHLC diario para pares USD/XXX y crosses.
Complementa el fetcher ECB que solo da EUR/XXX close.
Tickers formato XXXYYY=X (ej: USDJPY=X, GBPJPY=X).
"""

from datetime import date

import yfinance as yf
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.forex import CurrencyPair, ForexRate

# (base, quote, categoría, ticker_yfinance)
FOREX_PAIRS = [
    # ── Majors (G7 vs USD) ──────────────────
    ("EUR", "USD", "major", "EURUSD=X"),
    ("USD", "JPY", "major", "USDJPY=X"),
    ("GBP", "USD", "major", "GBPUSD=X"),
    ("USD", "CHF", "major", "USDCHF=X"),
    ("USD", "CAD", "major", "USDCAD=X"),
    ("AUD", "USD", "major", "AUDUSD=X"),
    ("NZD", "USD", "major", "NZDUSD=X"),
    # ── Minor (EM / secundarias vs USD) ─────
    ("USD", "CNY", "minor", "USDCNY=X"),
    ("USD", "BRL", "minor", "USDBRL=X"),
    ("USD", "MXN", "minor", "USDMXN=X"),
    ("USD", "INR", "minor", "USDINR=X"),
    ("USD", "KRW", "minor", "USDKRW=X"),
    ("USD", "TRY", "minor", "USDTRY=X"),
    ("USD", "ZAR", "minor", "USDZAR=X"),
    ("USD", "SGD", "minor", "USDSGD=X"),
    ("USD", "SEK", "minor", "USDSEK=X"),
    ("USD", "NOK", "minor", "USDNOK=X"),
    ("USD", "DKK", "minor", "USDDKK=X"),
    ("USD", "THB", "minor", "USDTHB=X"),
    ("USD", "IDR", "minor", "USDIDR=X"),
    ("USD", "MYR", "minor", "USDMYR=X"),
    ("USD", "PHP", "minor", "USDPHP=X"),
    ("USD", "TWD", "minor", "USDTWD=X"),
    ("USD", "HKD", "minor", "USDHKD=X"),
    ("USD", "CLP", "minor", "USDCLP=X"),
    ("USD", "COP", "minor", "USDCOP=X"),
    ("USD", "PEN", "minor", "USDPEN=X"),
    ("USD", "ARS", "minor", "USDARS=X"),
    ("USD", "EGP", "minor", "USDEGP=X"),
    ("USD", "NGN", "minor", "USDNGN=X"),
    ("USD", "KES", "minor", "USDKES=X"),
    ("USD", "CZK", "minor", "USDCZK=X"),
    ("USD", "HUF", "minor", "USDHUF=X"),
    ("USD", "PLN", "minor", "USDPLN=X"),
    ("USD", "RON", "minor", "USDRON=X"),
    ("USD", "ILS", "minor", "USDILS=X"),
    ("USD", "SAR", "minor", "USDSAR=X"),
    ("USD", "AED", "minor", "USDAED=X"),
    ("USD", "QAR", "minor", "USDQAR=X"),
    ("USD", "KWD", "minor", "USDKWD=X"),
    ("USD", "BHD", "minor", "USDBHD=X"),
    ("USD", "PKR", "minor", "USDPKR=X"),
    ("USD", "BDT", "minor", "USDBDT=X"),
    ("USD", "VND", "minor", "USDVND=X"),
    ("USD", "UAH", "minor", "USDUAH=X"),
    ("USD", "JOD", "minor", "USDJOD=X"),
    ("USD", "GHS", "minor", "USDGHS=X"),
    # ── EUR crosses ─────────────────────────
    ("EUR", "JPY", "cross", "EURJPY=X"),
    ("EUR", "GBP", "cross", "EURGBP=X"),
    ("EUR", "CHF", "cross", "EURCHF=X"),
    ("EUR", "AUD", "cross", "EURAUD=X"),
    ("EUR", "NZD", "cross", "EURNZD=X"),
    ("EUR", "CAD", "cross", "EURCAD=X"),
    ("EUR", "SEK", "cross", "EURSEK=X"),
    ("EUR", "NOK", "cross", "EURNOK=X"),
    ("EUR", "DKK", "cross", "EURDKK=X"),
    ("EUR", "PLN", "cross", "EURPLN=X"),
    ("EUR", "CZK", "cross", "EURCZK=X"),
    ("EUR", "HUF", "cross", "EURHUF=X"),
    ("EUR", "TRY", "cross", "EURTRY=X"),
    ("EUR", "ZAR", "cross", "EURZAR=X"),
    ("EUR", "SGD", "cross", "EURSGD=X"),
    ("EUR", "HKD", "cross", "EURHKD=X"),
    # ── GBP crosses ─────────────────────────
    ("GBP", "JPY", "cross", "GBPJPY=X"),
    ("GBP", "CHF", "cross", "GBPCHF=X"),
    ("GBP", "AUD", "cross", "GBPAUD=X"),
    ("GBP", "NZD", "cross", "GBPNZD=X"),
    ("GBP", "CAD", "cross", "GBPCAD=X"),
    ("GBP", "SGD", "cross", "GBPSGD=X"),
    ("GBP", "HKD", "cross", "GBPHKD=X"),
    # ── AUD crosses ─────────────────────────
    ("AUD", "JPY", "cross", "AUDJPY=X"),
    ("AUD", "NZD", "cross", "AUDNZD=X"),
    ("AUD", "CAD", "cross", "AUDCAD=X"),
    ("AUD", "CHF", "cross", "AUDCHF=X"),
    ("AUD", "SGD", "cross", "AUDSGD=X"),
    # ── NZD crosses ─────────────────────────
    ("NZD", "JPY", "cross", "NZDJPY=X"),
    ("NZD", "CHF", "cross", "NZDCHF=X"),
    ("NZD", "CAD", "cross", "NZDCAD=X"),
    # ── CAD / CHF / otros crosses ───────────
    ("CAD", "JPY", "cross", "CADJPY=X"),
    ("CAD", "CHF", "cross", "CADCHF=X"),
    ("CHF", "JPY", "cross", "CHFJPY=X"),
    ("SGD", "JPY", "cross", "SGDJPY=X"),
    ("TRY", "JPY", "cross", "TRYJPY=X"),
    ("ZAR", "JPY", "cross", "ZARJPY=X"),
    # ── Exóticos ────────────────────────────
    ("USD", "LKR", "exotic", "USDLKR=X"),
    ("USD", "KZT", "exotic", "USDKZT=X"),
    ("USD", "MAD", "exotic", "USDMAD=X"),
    ("USD", "TND", "exotic", "USDTND=X"),
    ("USD", "GEL", "exotic", "USDGEL=X"),
    ("USD", "RUB", "exotic", "USDRUB=X"),
    ("USD", "BGN", "exotic", "USDBGN=X"),
    ("USD", "ISK", "exotic", "USDISK=X"),
    ("USD", "JMD", "exotic", "USDJMD=X"),
    ("USD", "TTD", "exotic", "USDTTD=X"),
    ("USD", "DOP", "exotic", "USDDOP=X"),
    ("USD", "GTQ", "exotic", "USDGTQ=X"),
    ("USD", "HNL", "exotic", "USDHNL=X"),
    ("USD", "BOB", "exotic", "USDBOB=X"),
    ("USD", "PYG", "exotic", "USDPYG=X"),
    ("USD", "UYU", "exotic", "USDUYU=X"),
    ("USD", "CRC", "exotic", "USDCRC=X"),
    ("USD", "MUR", "exotic", "USDMUR=X"),
]

CHUNK = 10_000


class YFinanceForexFetcher(BaseFetcher):
    """Pares forex via yfinance (OHLC completo)."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "forex"
    RATE_LIMIT = 0.5

    def fetch(
        self,
        pair_code: str | None = None,
        period: str = "max",
    ) -> dict:
        """Descargar OHLC forex.

        Args:
            pair_code: Par específico (ej: USDJPY).
                None = todos los pares definidos.
            period: Periodo yfinance (max, 5y, 1y...).
        """
        run_id = self._start_run(
            params={
                "pair_code": pair_code,
                "period": period,
            }
        )
        session = get_session()
        total = 0
        errors = 0

        try:
            src_id = self._ensure_source(session)

            pairs_to_fetch = FOREX_PAIRS
            if pair_code:
                pairs_to_fetch = [
                    p for p in FOREX_PAIRS if f"{p[0]}{p[1]}" == pair_code
                ]

            for base, quote, cat, yf_tk in pairs_to_fetch:
                pair_id = self._ensure_pair(session, base, quote, cat)
                n = self._fetch_pair(
                    yf_tk,
                    pair_id,
                    src_id,
                    session,
                    period,
                )
                if n < 0:
                    errors += 1
                else:
                    total += n

            self._finish_run(
                run_id,
                "success",
                fetched=total,
                inserted=total,
                errors=errors,
            )
            logger.info(
                "Forex yfinance: %d pts, %d errores",
                total,
                errors,
            )
        except Exception as e:
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("Forex yfinance falló: %s", e)
            raise
        finally:
            session.close()

        return {"puntos": total, "errores": errors}

    def _fetch_pair(self, yf_ticker, pair_id, src_id, session, period) -> int:
        """Descarga OHLC de un par. -1 si error."""
        logger.info("  Forex yf: %s...", yf_ticker)

        try:
            t = yf.Ticker(yf_ticker)
            df = t.history(period=period)
        except Exception as e:
            logger.warning("  Error %s: %s", yf_ticker, e)
            return -1

        if df.empty:
            logger.warning("  Sin datos para %s", yf_ticker)
            return -1

        batch: list[dict] = []
        for idx, row in df.iterrows():
            dt = (
                idx.date()
                if hasattr(idx, "date")
                else date.fromisoformat(str(idx)[:10])
            )

            o = row.get("Open")
            h = row.get("High")
            lo = row.get("Low")
            c = row.get("Close")

            if c is None or c != c:
                continue

            batch.append(
                {
                    "pair_id": pair_id,
                    "date": dt,
                    "open": round(float(o), 8) if o == o else None,
                    "high": round(float(h), 8) if h == h else None,
                    "low": round(float(lo), 8) if lo == lo else None,
                    "close": round(float(c), 8),
                    "source_id": src_id,
                }
            )

        for i in range(0, len(batch), CHUNK):
            chunk = batch[i : i + CHUNK]
            stmt = insert(ForexRate).values(chunk)
            stmt = stmt.on_conflict_do_update(
                constraint=("rate_daily_pair_id_date_key"),
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "source_id": stmt.excluded.source_id,
                },
            )
            session.execute(stmt)
        if batch:
            session.commit()

        logger.info(
            "  %s: %d pts (%s a %s)",
            yf_ticker,
            len(batch),
            batch[0]["date"] if batch else "?",
            batch[-1]["date"] if batch else "?",
        )
        return len(batch)

    @staticmethod
    def _ensure_pair(session, base, quote, category) -> int:
        code = f"{base}{quote}"
        pair = session.query(CurrencyPair).filter_by(pair_code=code).first()
        if not pair:
            pair = CurrencyPair(
                base_currency=base,
                quote_currency=quote,
                pair_code=code,
                category=category,
            )
            session.add(pair)
            session.flush()
        return pair.id

    @staticmethod
    def _ensure_source(session) -> int:
        from stonks.models.meta import DataSource

        src = session.query(DataSource).filter_by(name="yfinance").first()
        if not src:
            src = DataSource(
                name="yfinance",
                display_name="Yahoo Finance",
                base_url="https://finance.yahoo.com/",
            )
            session.add(src)
            session.commit()
        return src.id
