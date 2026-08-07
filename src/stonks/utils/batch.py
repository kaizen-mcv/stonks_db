"""Descarga batch via yfinance.download()."""

import logging
import time

import pandas as pd
import yfinance as yf

log = logging.getLogger("stonks.batch")

BATCH_SIZE = 50
PAUSE_BETWEEN_BATCHES = 2.0  # segundos


def batch_download(
    tickers: list[str],
    period: str = "max",
    interval: str = "1d",
    batch_size: int = BATCH_SIZE,
    pause: float = PAUSE_BETWEEN_BATCHES,
    auto_adjust: bool = True,
) -> pd.DataFrame:
    """Descarga OHLCV en lotes via yf.download().

    Args:
        tickers: lista de símbolos
        period: período (max, 5y, 1y, etc.)
        interval: intervalo (1d, 1h, 5m, 1m)
        batch_size: tickers por lote
        pause: pausa entre lotes (segundos)
        auto_adjust: si es True (por defecto de yfinance) la columna
            Close viene ya ajustada por splits y dividendos y no hay
            columna "Adj Close". Poner False para obtener el cierre
            real y el ajustado por separado.

    La columna temporal se normaliza siempre a `ts`: yfinance la llama
    `Date` en diario y `Datetime` en intradia, y al concatenar lotes
    heterogeneos pandas creaba ambas columnas rellenando con NaT la que
    faltaba. Eso dejaba `ts` a nulo y reventaba la insercion en las
    tablas particionadas.

    Returns:
        DataFrame con MultiIndex (Date, Ticker) y columnas
        OHLCV. Tickers con error se excluyen silenciosamente.
    """
    frames = []
    total = len(tickers)
    n_batches = (total + batch_size - 1) // batch_size

    for i in range(0, total, batch_size):
        lote = tickers[i : i + batch_size]
        batch_num = i // batch_size + 1

        log.info(
            "Batch %d/%d (%d tickers): %s...",
            batch_num,
            n_batches,
            len(lote),
            lote[0],
        )

        try:
            df = yf.download(
                lote,
                period=period,
                interval=interval,
                group_by="ticker",
                threads=True,
                progress=False,
                auto_adjust=auto_adjust,
            )

            if df.empty:
                log.warning("Batch %d vacío", batch_num)
                continue

            if len(lote) == 1:
                # yf.download con 1 ticker no agrupa
                ticker = lote[0]
                df = df.copy()
                df["Ticker"] = ticker
                df.index.name = "ts"
                df = df.reset_index()
                frames.append(df)
            else:
                # MultiIndex columns: (ticker, OHLCV)
                for ticker in lote:
                    if ticker not in df.columns.get_level_values(0):
                        continue
                    sub = df[ticker].dropna(subset=["Close"], how="all")
                    if sub.empty:
                        continue
                    sub = sub.copy()
                    sub["Ticker"] = ticker
                    sub.index.name = "ts"
                    sub = sub.reset_index()
                    frames.append(sub)

        except Exception as e:
            log.error("Error en batch %d: %s", batch_num, e)

        if batch_num < n_batches:
            time.sleep(pause)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    log.info(
        "Descarga completa: %d filas, %d tickers",
        len(result),
        result["Ticker"].nunique(),
    )
    return result
