"""Fetcher intraday — descarga datos 1m/5m/1h via
yfinance y upsert en tablas particionadas."""

import logging

from sqlalchemy import text

from stonks.db import engine
from stonks.fetchers.base import BaseFetcher
from stonks.utils.batch import batch_download
from stonks.utils.partitions import ensure_partitions

log = logging.getLogger("stonks.intraday")

PERIOD_MAP = {
    "1m": "7d",
    "5m": "60d",
    "1h": "730d",
}

UPSERT_CHUNK = 10_000

UPSERT_SQL = text("""
    INSERT INTO equity.price_intraday
        (company_id, ts, interval, open, high,
         low, close, volume)
    VALUES
        (:company_id, :ts, :interval, :open, :high,
         :low, :close, :volume)
    ON CONFLICT (company_id, ts, interval) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume
""")


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


class IntradayFetcher(BaseFetcher):
    """Descarga intraday para equity."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "equity"
    RATE_LIMIT = 0.2

    def fetch(
        self,
        tickers: list[str],
        interval: str = "1h",
    ) -> dict[str, int]:
        """Descarga y upsert intraday.

        Args:
            tickers: lista de símbolos
            interval: '1m', '5m', '1h'

        Returns:
            {"fetched": N, "upserted": N, "errors": N}
        """
        period = PERIOD_MAP.get(interval, "7d")
        stats = {
            "fetched": 0,
            "upserted": 0,
            "errors": 0,
        }

        ensure_partitions(engine)

        # Mapa ticker → company_id
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT ticker, id FROM equity.company")
            ).fetchall()
        ticker_to_id = {r[0]: r[1] for r in rows}

        run_id = self._start_run(
            params={
                "interval": interval,
                "tickers_count": len(tickers),
            }
        )

        try:
            df = batch_download(
                tickers,
                period=period,
                interval=interval,
            )
            if df.empty:
                log.warning("Sin datos intraday")
                self._finish_run(run_id, "success")
                return stats

            stats["fetched"] = len(df)

            upsert_rows = []
            for _, row in df.iterrows():
                ticker = row.get("Ticker", "")
                cid = ticker_to_id.get(ticker)
                if cid is None:
                    continue
                close = _safe_float(row.get("Close"))
                if close is None:
                    continue

                ts = row.get("Datetime", row.get("Date"))
                upsert_rows.append(
                    {
                        "company_id": cid,
                        "ts": ts,
                        "interval": interval,
                        "open": _safe_float(row.get("Open")),
                        "high": _safe_float(row.get("High")),
                        "low": _safe_float(row.get("Low")),
                        "close": close,
                        "volume": (
                            int(float(row["Volume"]))
                            if _safe_float(row.get("Volume"))
                            else None
                        ),
                    }
                )

            with engine.begin() as conn:
                for j in range(0, len(upsert_rows), UPSERT_CHUNK):
                    chunk = upsert_rows[j : j + UPSERT_CHUNK]
                    conn.execute(UPSERT_SQL, chunk)
                    stats["upserted"] += len(chunk)

            log.info(
                "Intraday %s: %d fetched, %d upserted",
                interval,
                stats["fetched"],
                stats["upserted"],
            )
            self._finish_run(
                run_id,
                "success",
                fetched=stats["fetched"],
                inserted=stats["upserted"],
            )

        except Exception as e:
            stats["errors"] += 1
            log.error("Error intraday: %s", e)
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )

        return stats
