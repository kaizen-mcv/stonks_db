"""Orquestador de actualización por cadencia (daily/weekly/monthly).

Agrupa descargas y transformaciones en pasos aislados: si uno falla, se
registra (en meta.fetch_run / meta.transform_run) y se continúa. Al final
reconstruye la capa gold de forma idempotente.

Uso programático: run_update("weekly"). Desde CLI: `stonks update -c weekly`.

Nota: la ingesta de precios/macro ya existente sigue en los scripts
daily_update.sh / weekly_update.sh. Este pipeline orquesta las piezas
nuevas del medallion (sectores, y en fases B/C constituyentes, PIT,
analistas y macro no-US) más la reconstrucción de gold.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from stonks.logger import get_logger

logger = get_logger("stonks.pipeline")


@dataclass
class Step:
    """Un paso del pipeline: descargas + transformaciones."""

    name: str
    fetches: list[Callable] = field(default_factory=list)
    transforms: list[Callable] = field(default_factory=list)


def _fetcher(module: str, cls: str, method: str = "fetch", **kwargs):
    """Descarga genérica instanciando un fetcher por nombre (perezoso)."""

    def run():
        mod = __import__(f"stonks.fetchers.{module}", fromlist=[cls])
        getattr(getattr(mod, cls)(), method)(**kwargs)

    return run


def _transform(module: str, cls: str, **kwargs):
    """Transformación genérica (idempotente), import perezoso."""

    def run():
        mod = __import__(f"stonks.transform.{module}", fromlist=[cls])
        getattr(mod, cls)().transform(**kwargs)

    return run


# --- Definición del pipeline por cadencia ---
# Los pasos de las fases B y C se añaden a medida que aterrizan.

PIPELINE: dict[str, list[Step]] = {
    "daily": [
        # Foto diaria de analistas: el histórico se acumula hacia
        # adelante (yfinance no da serie retroactiva), por eso va a diario.
        Step(
            "analyst-snap",
            [_fetcher("analyst", "AnalystFetcher")],
            [_transform("analyst", "AnalystTransform")],
        ),
    ],
    "weekly": [
        Step(
            "sectors",
            [],
            [_transform("sectors", "SectorTransform")],
        ),
        Step(
            "constituents",
            [_fetcher("constituents", "ConstituentsFetcher")],
            [_transform("constituents", "MembershipTransform")],
        ),
        Step(
            "sec-pit",
            [_fetcher("sec_edgar", "SecEdgarFetcher", method="fetch_batch")],
            [_transform("fundamentals_pit", "FundamentalsPitTransform")],
        ),
    ],
    "monthly": [
        Step(
            "factors",
            [],
            [_transform("factors", "FactorScoreTransform")],
        ),
    ],
}

CADENCES = ("daily", "weekly", "monthly")


def run_update(
    cadence: str, dry_run: bool = False, build: bool = True
) -> dict:
    """Ejecutar el pipeline de una cadencia (o 'all').

    Cada paso se aísla: si uno falla se registra y se continúa. Devuelve
    un resumen {paso: estado}.
    """
    cadences = CADENCES if cadence == "all" else (cadence,)
    resumen: dict[str, str] = {}
    for cad in cadences:
        steps = PIPELINE.get(cad, [])
        logger.info("=== Cadencia %s: %d pasos ===", cad, len(steps))
        for step in steps:
            if dry_run:
                resumen[step.name] = "dry-run"
                logger.info("[dry-run] %s", step.name)
                continue
            try:
                for fn in step.fetches:
                    fn()
                for fn in step.transforms:
                    fn()
                resumen[step.name] = "ok"
                logger.info("Paso OK: %s", step.name)
            except Exception as e:  # noqa: BLE001
                resumen[step.name] = f"error: {e}"
                logger.error("Paso fallido %s: %s", step.name, e)

    # Reconstruir gold una vez al final (idempotente).
    if not dry_run and build:
        from stonks.gold.build import build_gold

        build_gold()
        resumen["gold"] = "ok"

    return resumen
