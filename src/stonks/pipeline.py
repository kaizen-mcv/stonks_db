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

import time
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
        Step(
            "analyst-snap",
            [_fetcher("analyst", "AnalystFetcher")],
            [_transform("analyst", "AnalystTransform")],
        ),
        Step(
            "options",
            [_fetcher("options", "OptionsFetcher")],
            [],
        ),
        Step(
            "forex-yfinance",
            [
                _fetcher(
                    "yfinance_forex",
                    "YFinanceForexFetcher",
                )
            ],
            [],
        ),
        Step(
            "volatility",
            [
                _fetcher(
                    "volatility",
                    "VolatilityFetcher",
                    method="seed_indices",
                ),
                _fetcher(
                    "volatility",
                    "VolatilityFetcher",
                    method="fetch_prices",
                    period="1y",
                ),
            ],
            [],
        ),
        Step(
            "index-futures",
            [
                _fetcher(
                    "index_futures",
                    "IndexFuturesFetcher",
                    method="seed_contracts",
                ),
                _fetcher(
                    "index_futures",
                    "IndexFuturesFetcher",
                    method="fetch_prices",
                    period="1y",
                ),
            ],
            [],
        ),
        Step(
            "intraday-crypto-1h",
            [
                _fetcher(
                    "intraday_multi",
                    "IntradayMultiFetcher",
                    domain="crypto",
                    interval="1h",
                ),
            ],
            [],
        ),
        Step(
            "intraday-forex-1h",
            [
                _fetcher(
                    "intraday_multi",
                    "IntradayMultiFetcher",
                    domain="forex",
                    interval="1h",
                ),
            ],
            [],
        ),
        Step(
            "intraday-commodity-1h",
            [
                _fetcher(
                    "intraday_multi",
                    "IntradayMultiFetcher",
                    domain="commodity",
                    interval="1h",
                ),
            ],
            [],
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
            [
                _fetcher(
                    "sec_edgar",
                    "SecEdgarFetcher",
                    method="fetch_batch",
                )
            ],
            [
                _transform(
                    "fundamentals_pit",
                    "FundamentalsPitTransform",
                )
            ],
        ),
        Step(
            "equity-deep",
            [_fetcher("equity_deep", "EquityDeepFetcher")],
            [],
        ),
        Step(
            "crypto-yfinance",
            [
                _fetcher(
                    "crypto_yfinance",
                    "CryptoYFinanceFetcher",
                )
            ],
            [],
        ),
        Step(
            "commodities",
            [_fetcher("commodities", "CommodityFetcher")],
            [],
        ),
        Step(
            "funds",
            [_fetcher("funds", "FundFetcher")],
            [],
        ),
    ],
    "monthly": [
        Step(
            "factors",
            [],
            [_transform("factors", "FactorScoreTransform")],
        ),
        # Macro de alta frecuencia (mensual/trimestral): tipos y crédito
        # (BIS) e inflación/paro/IP/PIB de la UE (Eurostat).
        Step(
            "macro-hf",
            [
                _fetcher("sdmx", "BISFetcher"),
                _fetcher("sdmx", "OECDFetcher"),
                _fetcher("eurostat", "EurostatFetcher"),
                _fetcher("ecb_sdw", "ECBSDWFetcher"),
                _fetcher("imf_ifs", "IMFIFSFetcher"),
                _fetcher("imf_bop", "IMFBOPFetcher"),
            ],
            [],
        ),
        # Vintages point-in-time (FRED/ALFRED) de las macro US clave:
        # reconstruye qué se sabía en cada momento (backtests sin sesgo).
        Step(
            "vintages",
            [_fetcher("fred", "FredFetcher", method="fetch_all_vintages")],
            [],
        ),
    ],
    "yearly": [
        # Economía mundial: cuentas nacionales, precios, fiscal,
        # externo y trabajo (IMF World Economic Outlook, ~200 países).
        Step(
            "imf-macro",
            [_fetcher("imf", "IMFDataMapperFetcher")],
            [
                _transform(
                    "macro_indicators",
                    "MacroIndicatorsTransform",
                    source_name="imf",
                )
            ],
        ),
        # Comercio internacional bilateral (World Bank WITS).
        Step(
            "trade",
            [_fetcher("wits", "WITSFetcher")],
            [_transform("trade", "TradeTransform")],
        ),
        # Comercio por producto HS2 (UN Comtrade). Requiere
        # STONKS_COMTRADE_KEY; si falta, el paso se salta sin romper.
        Step(
            "trade-hs",
            [_fetcher("comtrade", "ComtradeFetcher")],
            [],
        ),
        # Energía mundial por fuente (Our World in Data).
        Step(
            "energy",
            [_fetcher("owid", "OWIDEnergyFetcher")],
            [],
        ),
        # Energía internacional desglosada (EIA). Requiere
        # STONKS_EIA_KEY; si falta, el paso se salta sin romper.
        Step(
            "energy-eia",
            [_fetcher("eia", "EIAFetcher")],
            [],
        ),
        # Emisiones CO2/GHG (Our World in Data → macro).
        Step(
            "co2",
            [_fetcher("owid", "OWIDEnergyFetcher", method="fetch_co2")],
            [
                _transform(
                    "macro_indicators",
                    "MacroIndicatorsTransform",
                    source_name="owid",
                )
            ],
        ),
        # World Bank WDI completo (~1500 indicadores: desarrollo, salud,
        # educación, pobreza, medio ambiente, agricultura...).
        Step(
            "world-bank",
            [_fetcher("world_bank", "WorldBankFetcher")],
            [],
        ),
        # Agricultura: producción por cultivo/ganado (FAOSTAT).
        Step(
            "agri",
            [_fetcher("faostat", "FaostatFetcher")],
            [],
        ),
        # Salud global (WHO GHO) y desigualdad renta/riqueza (WID.world).
        Step(
            "health-wealth",
            [
                _fetcher("who", "WHOFetcher"),
                _fetcher("wid", "WIDFetcher"),
            ],
            [],
        ),
        # Trabajo: paro y participación (ILOSTAT, ~200-275 áreas).
        Step(
            "labor",
            [_fetcher("sdmx", "ILOFetcher")],
            [],
        ),
        # Productividad: TFP, capital humano (Penn World Table).
        Step(
            "productivity",
            [_fetcher("pwt", "PWTFetcher")],
            [],
        ),
        # Gobernanza: corrupción (TI CPI) y libertad (Freedom House).
        Step(
            "governance",
            [
                _fetcher("ti_cpi", "TICPIFetcher"),
                _fetcher(
                    "freedom_house",
                    "FreedomHouseFetcher",
                ),
            ],
            [],
        ),
        # Gobernanza extendida: fragilidad estatal (FSI).
        # Heritage se retiró en la auditoría 2026-08: su dominio
        # devuelve 403 a todo acceso automatizado (desafío Cloudflare).
        Step(
            "governance-ext",
            [
                _fetcher("fsi", "FSIFetcher"),
            ],
            [],
        ),
        # Gasto militar (SIPRI).
        Step(
            "military",
            [_fetcher("sipri", "SIPRIFetcher")],
            [],
        ),
        # Desarrollo humano (UNDP HDI/GDI/GII/MPI).
        Step(
            "development",
            [_fetcher("undp", "UNDPFetcher")],
            [],
        ),
        # Vulnerabilidad climática (ND-GAIN).
        Step(
            "climate",
            [_fetcher("ndgain", "NDGAINFetcher")],
            [],
        ),
        # Democracia detallada (V-Dem, 202 países).
        Step(
            "democracy",
            [_fetcher("vdem", "VDemFetcher")],
            [],
        ),
        # Demografía y proyecciones (UN DESA).
        Step(
            "population",
            [
                _fetcher(
                    "un_population",
                    "UNPopulationFetcher",
                ),
            ],
            [],
        ),
        # Innovación (WIPO patentes).
        Step(
            "innovation",
            [_fetcher("wipo", "WIPOFetcher")],
            [],
        ),
        # Educación detallada (UNESCO UIS).
        Step(
            "education",
            [_fetcher("unesco", "UNESCOFetcher")],
            [],
        ),
        # FDI y conectividad (UNCTAD).
        Step(
            "trade-detail",
            [_fetcher("unctad", "UNCTADFetcher")],
            [],
        ),
        # Comercio bilateral mensual (IMF DOTS).
        Step(
            "trade-dots",
            [_fetcher("imf_dots", "IMFDOTSFetcher")],
            [],
        ),
        # Finanzas públicas detalladas (IMF GFS).
        Step(
            "fiscal-detail",
            [_fetcher("imf_gfs", "IMFGFSFetcher")],
            [],
        ),
        # Emisiones sectoriales (EDGAR JRC).
        Step(
            "emissions",
            [
                _fetcher(
                    "edgar_emissions",
                    "EDGAREmissionsFetcher",
                ),
            ],
            [],
        ),
    ],
}

CADENCES = ("daily", "weekly", "monthly", "yearly")

MAX_STEP_RETRIES = 1
RETRY_DELAY = 5


def _run_step(step: Step) -> None:
    """Ejecutar un paso con 1 reintento."""
    for attempt in range(1, MAX_STEP_RETRIES + 2):
        try:
            for fn in step.fetches:
                fn()
            for fn in step.transforms:
                fn()
            return
        except Exception:
            if attempt > MAX_STEP_RETRIES:
                raise
            logger.warning(
                "Reintentando %s en %ds...",
                step.name,
                RETRY_DELAY,
            )
            time.sleep(RETRY_DELAY)


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
                _run_step(step)
                resumen[step.name] = "ok"
                logger.info("Paso OK: %s", step.name)
            except Exception as e:  # noqa: BLE001
                resumen[step.name] = f"error: {e}"
                logger.error(
                    "Paso fallido %s: %s",
                    step.name,
                    e,
                )

    # Reconstruir gold una vez al final (idempotente).
    if not dry_run and build:
        from stonks.gold.build import build_gold

        build_gold()
        resumen["gold"] = "ok"

    return resumen
