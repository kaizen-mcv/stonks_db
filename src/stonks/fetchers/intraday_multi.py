"""Fetcher intraday multi-dominio — descarga datos
1m/5m/1h para crypto, forex y commodities."""

import logging

from sqlalchemy import text

from stonks.db import engine
from stonks.fetchers.base import BaseFetcher
from stonks.utils.batch import batch_download
from stonks.utils.partitions import ensure_partitions

log = logging.getLogger("stonks.intraday_multi")

PERIOD_MAP = {
    "1m": "7d",
    "5m": "60d",
    "1h": "730d",
}

UPSERT_CHUNK = 10_000


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


CRYPTO_UPSERT = text("""
    INSERT INTO crypto.price_intraday
        (coin_id, ts, interval, open, high,
         low, close, volume_usd)
    VALUES
        (:ref_id, :ts, :interval, :open, :high,
         :low, :close, :volume)
    ON CONFLICT (coin_id, ts, interval) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume_usd = EXCLUDED.volume_usd
""")

FOREX_UPSERT = text("""
    INSERT INTO forex.rate_intraday
        (pair_id, ts, interval, open, high,
         low, close)
    VALUES
        (:ref_id, :ts, :interval, :open, :high,
         :low, :close)
    ON CONFLICT (pair_id, ts, interval) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close
""")

COMMODITY_UPSERT = text("""
    INSERT INTO commodity.price_intraday
        (commodity_id, ts, interval, open, high,
         low, close, volume)
    VALUES
        (:ref_id, :ts, :interval, :open, :high,
         :low, :close, :volume)
    ON CONFLICT (commodity_id, ts, interval)
    DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume
""")

DOMAIN_CONFIG = {
    "crypto": {
        "upsert_sql": CRYPTO_UPSERT,
        "ticker_query": ("SELECT symbol, id FROM crypto.coin"),
        "ticker_fmt": "{}-USD",
        "tables": ["crypto.price_intraday"],
        "has_volume": True,
    },
    "forex": {
        "upsert_sql": FOREX_UPSERT,
        "ticker_query": ("SELECT pair_code, id FROM forex.currency_pair"),
        "ticker_fmt": "{}=X",
        "tables": ["forex.rate_intraday"],
        "has_volume": False,
    },
    "commodity": {
        "upsert_sql": COMMODITY_UPSERT,
        "ticker_query": (
            "SELECT yfinance_ticker, id "
            "FROM commodity.commodity "
            "WHERE yfinance_ticker IS NOT NULL"
        ),
        "ticker_fmt": "{}",
        "tables": ["commodity.price_intraday"],
        "has_volume": True,
    },
}


class IntradayMultiFetcher(BaseFetcher):
    """Intraday para crypto, forex y commodities."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "intraday_multi"
    RATE_LIMIT = 0.2

    def fetch(
        self,
        domain: str,
        interval: str = "1h",
        tickers: list[str] | None = None,
    ) -> dict[str, int]:
        """Descarga y upsert intraday.

        Args:
            domain: 'crypto', 'forex', 'commodity'
            interval: '1m', '5m', '1h'
            tickers: lista de claves (symbol,
                pair_code, o yf_ticker). None = todos.
        """
        cfg = DOMAIN_CONFIG[domain]
        period = PERIOD_MAP.get(interval, "7d")
        stats = {
            "fetched": 0,
            "upserted": 0,
            "errors": 0,
        }

        ensure_partitions(engine, tables=cfg["tables"])

        with engine.connect() as conn:
            rows = conn.execute(text(cfg["ticker_query"])).fetchall()
        key_to_id = {r[0]: r[1] for r in rows}

        if tickers:
            key_to_id = {k: v for k, v in key_to_id.items() if k in tickers}

        if domain == "commodity":
            yf_tickers = list(key_to_id.keys())
            yf_to_id = key_to_id
        else:
            yf_tickers = [cfg["ticker_fmt"].format(k) for k in key_to_id]
            yf_to_id = {
                cfg["ticker_fmt"].format(k): v for k, v in key_to_id.items()
            }

        run_id = self._start_run(
            params={
                "domain": domain,
                "interval": interval,
                "count": len(yf_tickers),
            }
        )

        try:
            df = batch_download(
                yf_tickers,
                period=period,
                interval=interval,
            )
            if df.empty:
                log.warning("Sin datos intraday %s", domain)
                self._finish_run(run_id, "success")
                return stats

            stats["fetched"] = len(df)
            upsert_rows = []

            for _, row in df.iterrows():
                ticker = row.get("Ticker", "")
                ref_id = yf_to_id.get(ticker)
                if ref_id is None:
                    continue
                close = _safe_float(row.get("Close"))
                if close is None:
                    continue

                ts = row.get("Datetime", row.get("Date"))
                entry = {
                    "ref_id": ref_id,
                    "ts": ts,
                    "interval": interval,
                    "open": _safe_float(row.get("Open")),
                    "high": _safe_float(row.get("High")),
                    "low": _safe_float(row.get("Low")),
                    "close": close,
                }
                if cfg["has_volume"]:
                    v = _safe_float(row.get("Volume"))
                    entry["volume"] = int(v) if v else None

                upsert_rows.append(entry)

            with engine.begin() as conn:
                for j in range(0, len(upsert_rows), UPSERT_CHUNK):
                    chunk = upsert_rows[j : j + UPSERT_CHUNK]
                    conn.execute(cfg["upsert_sql"], chunk)
                    stats["upserted"] += len(chunk)

            log.info(
                "Intraday %s %s: %d → %d upserted",
                domain,
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
            log.error("Error intraday %s: %s", domain, e)
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )

        return stats
