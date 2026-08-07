"""Recargar equity.price_daily con el cierre real y el ajustado.

Hasta la auditoria de datos de 2026-08, `equity.price_daily.close`
guardaba el precio YA ajustado por splits y dividendos (yfinance aplica
`auto_adjust=True` por defecto) y `adj_close` estaba vacia en los 24
millones de filas. El ajuste retroactivo llegaba a generar precios
negativos en valores con muchos dividendos acumulados.

Este script vuelve a descargar el universo con `auto_adjust=False`, de
modo que cada columna signifique lo que dice su nombre.

Se procesa por tandas de tickers y se guarda el progreso en disco: la
descarga completa son horas y hay que poder reanudarla. Cada ticker
queda entero en el regimen nuevo o entero en el viejo, nunca a medias,
porque el upsert reemplaza la fila completa por (company_id, date).

Uso:
    python scripts/recargar_precios_sin_ajustar.py [--tanda 400]
"""

import argparse
import json
import logging
from pathlib import Path

from sqlalchemy import text

from stonks.config import settings
from stonks.db import get_session
from stonks.fetchers.yfinance_ import YFinanceFetcher
from stonks.logger import setup_logger

log = logging.getLogger("stonks.recarga")

ESTADO = settings.state_dir / "recarga_precios.json"


def _tickers_pendientes() -> list[str]:
    """Tickers con precios cargados que aun no se han recargado."""
    session = get_session()
    try:
        filas = session.execute(
            text(
                "SELECT DISTINCT c.ticker FROM equity.company c "
                "WHERE c.ticker IS NOT NULL "
                "AND EXISTS (SELECT 1 FROM equity.price_daily p "
                "            WHERE p.company_id = c.id) "
                "ORDER BY c.ticker"
            )
        ).fetchall()
    finally:
        session.close()

    todos = [f[0] for f in filas]
    hechos = set(_estado().get("hechos", []))
    return [t for t in todos if t not in hechos]


def _estado() -> dict:
    if ESTADO.exists():
        return json.loads(ESTADO.read_text())
    return {"hechos": []}


def _guardar(hechos: list[str]) -> None:
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps({"hechos": hechos}))


def main(tanda: int) -> None:
    setup_logger("stonks.fetch")
    pendientes = _tickers_pendientes()
    hechos = _estado().get("hechos", [])

    log.warning(
        "Recarga: %d tickers pendientes (%d ya hechos)",
        len(pendientes),
        len(hechos),
    )

    fetcher = YFinanceFetcher()
    for i in range(0, len(pendientes), tanda):
        lote = pendientes[i : i + tanda]
        log.warning(
            "Tanda %d/%d (%d tickers)",
            i // tanda + 1,
            (len(pendientes) + tanda - 1) // tanda,
            len(lote),
        )
        try:
            resultado = fetcher.fetch_prices_bulk(lote, period="max")
            log.warning("  %s", resultado)
        except Exception as e:  # noqa: BLE001
            # Una tanda fallida no debe abortar la recarga entera:
            # se reintenta en la siguiente ejecucion.
            log.error("  tanda fallida: %s", e)
            continue

        hechos.extend(lote)
        _guardar(hechos)

    log.warning("Recarga terminada: %d tickers procesados", len(hechos))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tanda",
        type=int,
        default=400,
        help="tickers por tanda (por defecto 400)",
    )
    main(parser.parse_args().tanda)
