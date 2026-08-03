"""Fetcher de precios crypto via yfinance.

Descarga OHLCV diario con histórico completo (period=max)
usando tickers formato SYMBOL-USD. Complementa CoinGecko
que solo da close y max 365 días en free tier.

yfinance ofrece: BTC desde 2014, ETH desde 2017, etc.
"""

from datetime import date

import yfinance as yf
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.crypto import Coin, CryptoPrice

CHUNK = 10_000


class CryptoYFinanceFetcher(BaseFetcher):
    """Precios OHLCV crypto via yfinance."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "crypto"
    RATE_LIMIT = 0.5

    def fetch(
        self,
        symbol: str | None = None,
        period: str = "max",
    ) -> dict:
        """Descargar OHLCV de todas las coins.

        Args:
            symbol: Símbolo específico (ej: BTC).
                None = todas las coins en BD.
            period: Periodo yfinance (max, 5y, 1y...).
        """
        run_id = self._start_run(params={"symbol": symbol, "period": period})
        session = get_session()
        total = 0
        errors = 0

        try:
            src = self._ensure_source(session)

            if symbol:
                coins = (
                    session.query(Coin).filter_by(symbol=symbol.upper()).all()
                )
            else:
                coins = session.query(Coin).all()

            for coin in coins:
                n = self._fetch_coin(coin, session, src, period)
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
                "Crypto yfinance total: %d pts, %d errores",
                total,
                errors,
            )
        except Exception as e:
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("Crypto yfinance falló: %s", e)
            raise
        finally:
            session.close()

        return {"puntos": total, "errores": errors}

    def _fetch_coin(self, coin, session, src_id, period) -> int:
        """Descarga OHLCV de una coin. -1 si error."""
        ticker = f"{coin.symbol}-USD"
        logger.info(
            "  Crypto yf: %s (%s)...",
            coin.name,
            ticker,
        )

        try:
            t = yf.Ticker(ticker)
            df = t.history(period=period)
        except Exception as e:
            logger.warning("  Error %s: %s", ticker, e)
            return -1

        if df.empty:
            logger.warning("  Sin datos para %s", ticker)
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
            v = row.get("Volume")

            if c is None or c != c:  # NaN check
                continue

            batch.append(
                {
                    "coin_id": coin.id,
                    "date": dt,
                    "open": round(float(o), 8) if o == o else None,
                    "high": round(float(h), 8) if h == h else None,
                    "low": round(float(lo), 8) if lo == lo else None,
                    "close": round(float(c), 8),
                    "volume_usd": round(float(v), 2) if v == v else None,
                }
            )

        for i in range(0, len(batch), CHUNK):
            chunk = batch[i : i + CHUNK]
            stmt = insert(CryptoPrice).values(chunk)
            stmt = stmt.on_conflict_do_update(
                constraint="price_daily_coin_id_date_key",
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume_usd": stmt.excluded.volume_usd,
                },
            )
            session.execute(stmt)
        if batch:
            session.commit()

        logger.info(
            "  %s: %d pts (%s a %s)",
            coin.symbol,
            len(batch),
            batch[0]["date"] if batch else "?",
            batch[-1]["date"] if batch else "?",
        )
        return len(batch)

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
