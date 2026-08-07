"""Fetcher para FRED (Federal Reserve Economic Data)."""

from datetime import date

from sqlalchemy import and_

import stonks.models  # noqa: F401
from stonks.config import settings
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.alternative import (
    SentimentIndicator,
    SentimentValue,
)
from stonks.models.fixed_income import YieldCurve
from stonks.models.macro import (
    DataPoint,
    Indicator,
    Series,
)
from stonks.models.meta import DataSource
from stonks.seed.unidades import normalizar_unidad

# Series FRED con frecuencia mensual/diaria
# (code_interno, fred_series_id, descripcion,
#  dominio, frecuencia)
FRED_SERIES = [
    # Tipos de interés de bancos centrales
    (
        "FED_FUNDS_RATE",
        "FEDFUNDS",
        "Federal Funds Effective Rate",
        "macro",
        "monthly",
    ),
    (
        "FED_FUNDS_UPPER",
        "DFEDTARU",
        "Fed Funds Upper Target",
        "macro",
        "daily",
    ),
    (
        "ECB_MAIN_RATE",
        "ECBMRRFR",
        "ECB Main Refinancing Rate",
        "macro",
        "monthly",
    ),
    (
        "BOJ_RATE",
        "IRSTCI01JPM156N",
        "Japan Short-Term Rate",
        "macro",
        "monthly",
    ),
    ("BOE_RATE", "BOERUKM", "Bank of England Rate", "macro", "monthly"),
    # Inflación mensual US
    ("US_CPI_MOM", "CPIAUCSL", "US CPI Urban All Items", "macro", "monthly"),
    (
        "US_CORE_CPI",
        "CPILFESL",
        "US Core CPI (ex food/energy)",
        "macro",
        "monthly",
    ),
    ("US_PCE", "PCEPI", "US PCE Price Index", "macro", "monthly"),
    (
        "US_CORE_PCE",
        "PCEPILFE",
        "US Core PCE (ex food/energy)",
        "macro",
        "monthly",
    ),
    # Empleo mensual US
    ("US_UNEMPLOYMENT", "UNRATE", "US Unemployment Rate", "macro", "monthly"),
    (
        "US_NONFARM_PAYROLLS",
        "PAYEMS",
        "US Total Nonfarm Payrolls",
        "macro",
        "monthly",
    ),
    (
        "US_INITIAL_CLAIMS",
        "ICSA",
        "US Initial Jobless Claims",
        "macro",
        "weekly",
    ),
    # PIB trimestral US
    (
        "US_GDP_QUARTERLY",
        "GDP",
        "US GDP (nominal, quarterly)",
        "macro",
        "quarterly",
    ),
    (
        "US_GDP_GROWTH",
        "A191RL1Q225SBEA",
        "US Real GDP Growth Rate",
        "macro",
        "quarterly",
    ),
    # Producción / actividad
    (
        "US_INDUSTRIAL_PROD",
        "INDPRO",
        "US Industrial Production Index",
        "macro",
        "monthly",
    ),
    ("US_CAPACITY_UTIL", "TCU", "US Capacity Utilization", "macro", "monthly"),
    (
        "US_PMI_MANUF",
        "MANEMP",
        "US Manufacturing Employment",
        "macro",
        "monthly",
    ),
    # Vivienda
    ("US_HOUSING_STARTS", "HOUST", "US Housing Starts", "macro", "monthly"),
    (
        "US_EXISTING_HOME_SALES",
        "EXHOSLUSM495S",
        "US Existing Home Sales",
        "macro",
        "monthly",
    ),
    (
        "CASE_SHILLER_US",
        "CSUSHPINSA",
        "S&P/Case-Shiller US Home Price",
        "alt",
        "monthly",
    ),
    # Consumo / confianza
    (
        "US_RETAIL_SALES",
        "RSXFS",
        "US Advance Retail Sales",
        "macro",
        "monthly",
    ),
    (
        "US_CONSUMER_SENTIMENT",
        "UMCSENT",
        "U Michigan Consumer Sentiment",
        "alt",
        "monthly",
    ),
    # Yields diarios US Treasury
    ("UST_3M", "DGS3MO", "US Treasury 3-Month Yield", "fi", "daily"),
    ("UST_2Y", "DGS2", "US Treasury 2-Year Yield", "fi", "daily"),
    ("UST_5Y", "DGS5", "US Treasury 5-Year Yield", "fi", "daily"),
    ("UST_10Y", "DGS10", "US Treasury 10-Year Yield", "fi", "daily"),
    ("UST_30Y", "DGS30", "US Treasury 30-Year Yield", "fi", "daily"),
    # Spreads
    ("SPREAD_10Y2Y", "T10Y2Y", "10Y-2Y Treasury Spread", "fi", "daily"),
    ("SPREAD_10Y3M", "T10Y3M", "10Y-3M Treasury Spread", "fi", "daily"),
    (
        "HY_SPREAD",
        "BAMLH0A0HYM2",
        "ICE BofA US High Yield Spread",
        "fi",
        "daily",
    ),
    (
        "IG_SPREAD",
        "BAMLC0A0CM",
        "ICE BofA US Corporate IG Spread",
        "fi",
        "daily",
    ),
    # Otros yields internacionales
    (
        "DE_10Y",
        "IRLTLT01DEM156N",
        "Germany 10-Year Bond Yield",
        "fi",
        "monthly",
    ),
    ("JP_10Y", "IRLTLT01JPM156N", "Japan 10-Year Bond Yield", "fi", "monthly"),
    ("GB_10Y", "IRLTLT01GBM156N", "UK 10-Year Bond Yield", "fi", "monthly"),
    # Oferta monetaria
    ("US_M2", "M2SL", "US M2 Money Stock", "macro", "monthly"),
    # Commodities (precio diario via FRED)
    (
        "GOLD_LONDON_FIX",
        "GOLDAMGBD228NLBM",
        "Gold Fixing Price London",
        "commodity",
        "daily",
    ),
    (
        "OIL_WTI_SPOT",
        "DCOILWTICO",
        "Crude Oil WTI Spot Price",
        "commodity",
        "daily",
    ),
    (
        "OIL_BRENT_SPOT",
        "DCOILBRENTEU",
        "Crude Oil Brent Spot Price",
        "commodity",
        "daily",
    ),
    # Breakeven inflation
    ("BREAKEVEN_5Y", "T5YIE", "5-Year Breakeven Inflation", "fi", "daily"),
    ("BREAKEVEN_10Y", "T10YIE", "10-Year Breakeven Inflation", "fi", "daily"),
    # Tipo real
    (
        "REAL_RATE_10Y",
        "REAINTRATREARAT10Y",
        "10-Year Real Interest Rate",
        "fi",
        "monthly",
    ),
    # Índices de bonos corporativos / spreads de crédito (ICE BofA)
    (
        "BOND_IG_OAS",
        "BAMLC0A0CM",
        "US Corporate IG OAS",
        "fixed_income",
        "daily",
    ),
    (
        "BOND_HY_OAS",
        "BAMLH0A0HYM2",
        "US High Yield OAS",
        "fixed_income",
        "daily",
    ),
    (
        "BOND_AAA_OAS",
        "BAMLC0A1CAAA",
        "US Corporate AAA OAS",
        "fixed_income",
        "daily",
    ),
    (
        "BOND_BBB_OAS",
        "BAMLC0A4CBBB",
        "US Corporate BBB OAS",
        "fixed_income",
        "daily",
    ),
    (
        "BOND_CCC_OAS",
        "BAMLH0A3HYC",
        "US CCC & Lower OAS",
        "fixed_income",
        "daily",
    ),
    (
        "BOND_IG_YIELD",
        "BAMLC0A0CMEY",
        "US Corporate IG Yield",
        "fixed_income",
        "daily",
    ),
    (
        "BOND_HY_YIELD",
        "BAMLH0A0HYM2EY",
        "US High Yield Yield",
        "fixed_income",
        "daily",
    ),
    (
        "BOND_EM_OAS",
        "BAMLEMCBPIOAS",
        "EM Corporate OAS",
        "fixed_income",
        "daily",
    ),
    # Inmobiliario (índices de precios de vivienda)
    (
        "HPI_CASE_SHILLER",
        "CSUSHPINSA",
        "Case-Shiller US Home Price Index",
        "real_estate",
        "monthly",
    ),
    (
        "HPI_CS_20CITY",
        "SPCS20RSA",
        "Case-Shiller 20-City Index",
        "real_estate",
        "monthly",
    ),
    (
        "HPI_FHFA",
        "USSTHPI",
        "FHFA House Price Index",
        "real_estate",
        "quarterly",
    ),
    (
        "HOME_MEDIAN_PRICE",
        "MSPUS",
        "Median Sales Price Houses",
        "real_estate",
        "quarterly",
    ),
    (
        "HOMEOWNERSHIP_RATE",
        "RHORUSQ156N",
        "US Homeownership Rate",
        "real_estate",
        "quarterly",
    ),
    # Gas natural Henry Hub (más histórico que yfinance)
    (
        "NATGAS_HH",
        "DHHNGSP",
        "Henry Hub Natural Gas Spot",
        "commodity",
        "daily",
    ),
    # Índice de precios de commodities del FMI
    (
        "IMF_COMMODITY_IDX",
        "PALLFNFINDEXM",
        "All Commodity Price Index (IMF)",
        "commodity",
        "monthly",
    ),
    # USD trade-weighted (proxy DXY)
    (
        "USD_INDEX",
        "DTWEXBGS",
        "Trade Weighted USD Index (Broad)",
        "macro",
        "daily",
    ),
    # Leading Economic Index (indicador adelantado US)
    (
        "US_LEI",
        "USSLIND",
        "Leading Economic Index (US)",
        "macro",
        "monthly",
    ),
    # Confianza del consumidor (OECD via FRED)
    (
        "US_CONSUMER_CONF",
        "CSCICP03USM665S",
        "Consumer Confidence (OECD/US)",
        "alt",
        "monthly",
    ),
    # Tipo real a 1 año
    (
        "REAL_RATE_1Y",
        "REAINTRATREARAT1YE",
        "1-Year Real Interest Rate",
        "fi",
        "monthly",
    ),
    # Money market
    (
        "SOFR",
        "SOFR",
        "Secured Overnight Financing Rate",
        "fi",
        "daily",
    ),
    (
        "FED_FUNDS_DAILY",
        "DFF",
        "Federal Funds Effective Rate (daily)",
        "fi",
        "daily",
    ),
    (
        "TED_SPREAD",
        "TEDRATE",
        "TED Spread (disc. 2021)",
        "fi",
        "daily",
    ),
    # Forex USD pairs (complementa ECB EUR-only)
    (
        "USD_EUR",
        "DEXUSEU",
        "USD/EUR Exchange Rate",
        "macro",
        "daily",
    ),
    (
        "USD_JPY",
        "DEXJPUS",
        "USD/JPY Exchange Rate",
        "macro",
        "daily",
    ),
    (
        "USD_GBP",
        "DEXUSUK",
        "USD/GBP Exchange Rate",
        "macro",
        "daily",
    ),
    (
        "USD_CHF",
        "DEXSZUS",
        "USD/CHF Exchange Rate",
        "macro",
        "daily",
    ),
    (
        "USD_CNY",
        "DEXCHUS",
        "USD/CNY Exchange Rate",
        "macro",
        "daily",
    ),
    (
        "USD_BRL",
        "DEXBZUS",
        "USD/BRL Exchange Rate",
        "macro",
        "daily",
    ),
    (
        "USD_INR",
        "DEXINUS",
        "USD/INR Exchange Rate",
        "macro",
        "daily",
    ),
    (
        "USD_MXN",
        "DEXMXUS",
        "USD/MXN Exchange Rate",
        "macro",
        "daily",
    ),
    # Eurozona vía OECD/FRED
    (
        "EURIBOR_3M",
        "IR3TIB01EZM156N",
        "3-Month EURIBOR (Eurozone)",
        "fi",
        "monthly",
    ),
    (
        "ESTR_RATE",
        "ECBESTRVOLWGTTRMDMNRT",
        "Euro Short-Term Rate (daily)",
        "fi",
        "daily",
    ),
    (
        "EZ_10Y",
        "IRLTLT01EZM156N",
        "Eurozone 10-Year Bond Yield",
        "fi",
        "monthly",
    ),
]

# Series clave para vintages point-in-time (ALFRED). Son las macro
# que más se revisan y las que interesa reconstruir sin sesgo de
# revisión en backtests: (code_interno, fred_series_id).
VINTAGE_SERIES = [
    ("US_GDP_QUARTERLY", "GDP"),
    ("US_GDP_GROWTH", "A191RL1Q225SBEA"),
    ("US_CPI_MOM", "CPIAUCSL"),
    ("US_CORE_CPI", "CPILFESL"),
    ("US_PCE", "PCEPI"),
    ("US_CORE_PCE", "PCEPILFE"),
    ("US_UNEMPLOYMENT", "UNRATE"),
    ("US_NONFARM_PAYROLLS", "PAYEMS"),
    ("US_INDUSTRIAL_PROD", "INDPRO"),
    ("US_RETAIL_SALES", "RSXFS"),
]

# Mapeo maturity para yields -> meses
YIELD_MATURITY = {
    "UST_3M": 3,
    "UST_2Y": 24,
    "UST_5Y": 60,
    "UST_10Y": 120,
    "UST_30Y": 360,
}


class FredFetcher(BaseFetcher):
    """Descarga datos de FRED."""

    SOURCE_NAME = "fred"
    DOMAIN = "macro"
    RATE_LIMIT = 0.5  # 120 req/min
    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = settings.fred_api_key
        if not self.api_key:
            logger.warning(
                "FRED API key no configurada. "
                "Regístrate en fred.stlouisfed.org"
            )

    def _fred_get(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> dict:
        """GET a la API de FRED."""
        if not self.api_key:
            raise ValueError("STONKS_FRED_API_KEY no configurada")
        url = f"{self.BASE_URL}/{endpoint}"
        if params is None:
            params = {}
        params["api_key"] = self.api_key
        params["file_type"] = "json"
        return self._get(url, params)

    def fetch_series(
        self,
        fred_id: str,
        code: str,
        domain: str = "macro",
        start_date: str = "2000-01-01",
    ) -> dict[str, int]:
        """Descargar una serie de FRED."""
        stats = {
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
        }
        session = get_session()

        try:
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            src_id = src.id if src else None

            data = self._fred_get(
                "series/observations",
                params={
                    "series_id": fred_id,
                    "observation_start": start_date,
                    "sort_order": "asc",
                },
            )

            observations = data.get("observations", [])

            # Guardar según dominio
            if domain == "fi" and code in (YIELD_MATURITY):
                # Yield curves
                maturity = YIELD_MATURITY[code]
                for obs in observations:
                    val = obs.get("value", ".")
                    if val == ".":
                        continue
                    stats["fetched"] += 1
                    dt = date.fromisoformat(obs["date"])
                    exists = (
                        session.query(YieldCurve)
                        .filter(
                            and_(
                                YieldCurve.country_code == "USA",
                                YieldCurve.date == dt,
                                YieldCurve.maturity_months == maturity,
                            )
                        )
                        .first()
                    )
                    if exists:
                        continue
                    session.add(
                        YieldCurve(
                            country_code="USA",
                            date=dt,
                            maturity_months=maturity,
                            yield_pct=float(val),
                            source_id=src_id,
                        )
                    )
                    stats["inserted"] += 1

            elif domain == "alt":
                # Sentimiento / housing
                ind = (
                    session.query(SentimentIndicator)
                    .filter_by(code=code)
                    .first()
                )
                if not ind:
                    ind = SentimentIndicator(
                        code=code,
                        name=code,
                    )
                    session.add(ind)
                    session.flush()

                for obs in observations:
                    val = obs.get("value", ".")
                    if val == ".":
                        continue
                    stats["fetched"] += 1
                    dt = date.fromisoformat(obs["date"])
                    exists = (
                        session.query(SentimentValue)
                        .filter(
                            and_(
                                SentimentValue.indicator_id == ind.id,
                                SentimentValue.date == dt,
                            )
                        )
                        .first()
                    )
                    if exists:
                        continue
                    session.add(
                        SentimentValue(
                            indicator_id=ind.id,
                            date=dt,
                            value=float(val),
                        )
                    )
                    stats["inserted"] += 1

            else:
                # Macro genérico → macro.data_point
                ind = session.query(Indicator).filter_by(code=code).first()
                if not ind:
                    # Buscar descripción
                    desc = code
                    for c, _fid, d, _, _ in FRED_SERIES:
                        if c == code:
                            desc = d
                            break
                    ind = Indicator(
                        code=code,
                        name=desc,
                        category="FRED",
                        frequency="monthly",
                    )
                    session.add(ind)
                    session.flush()

                series = (
                    session.query(Series)
                    .filter_by(
                        indicator_id=ind.id,
                        country_code="USA",
                        region_code=None,
                    )
                    .first()
                )
                if not series:
                    series = Series(
                        indicator_id=ind.id,
                        country_code="USA",
                        point_count=0,
                    )
                    session.add(series)
                    session.flush()

                for obs in observations:
                    val = obs.get("value", ".")
                    if val == ".":
                        continue
                    stats["fetched"] += 1
                    dt = date.fromisoformat(obs["date"])
                    exists = (
                        session.query(DataPoint)
                        .filter(
                            and_(
                                DataPoint.series_id == series.id,
                                DataPoint.date == dt,
                            )
                        )
                        .first()
                    )
                    if exists:
                        continue
                    session.add(
                        DataPoint(
                            series_id=series.id,
                            date=dt,
                            value=float(val),
                            source_id=src_id,
                        )
                    )
                    series.point_count += 1
                    stats["inserted"] += 1

                if series and observations:
                    last = [
                        o for o in observations if o.get("value", ".") != "."
                    ]
                    if last:
                        series.last_date = date.fromisoformat(last[-1]["date"])
                        series.last_value = float(last[-1]["value"])

            session.commit()

        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error FRED %s: %s", fred_id, e)
        finally:
            session.close()

        return stats

    def fetch_vintages(
        self,
        fred_id: str,
        code: str,
    ) -> dict[str, int]:
        """Descargar todas las vintages (ALFRED) de una serie a macro.

        Pide el histórico real-time completo: la API devuelve una fila
        por (fecha_obs, fecha_publicación). Se guarda en
        `macro.data_point_vintage` con upsert idempotente.
        """
        from sqlalchemy.dialects.postgresql import insert

        from stonks.models.macro import DataPointVintage

        stats = {"fetched": 0, "inserted": 0, "errors": 0}
        session = get_session()
        try:
            ind = session.query(Indicator).filter_by(code=code).first()
            if not ind:
                logger.warning("vintages: indicador %s no existe aún", code)
                return stats
            series = (
                session.query(Series)
                .filter_by(
                    indicator_id=ind.id,
                    country_code="USA",
                    region_code=None,
                )
                .first()
            )
            if not series:
                logger.warning("vintages: serie %s/USA no existe aún", code)
                return stats

            data = self._fred_get(
                "series/observations",
                params={
                    "series_id": fred_id,
                    "realtime_start": "1776-07-04",
                    "realtime_end": "9999-12-31",
                    "sort_order": "asc",
                },
            )
            observations = data.get("observations", [])
            filas = []
            for obs in observations:
                val = obs.get("value", ".")
                if val == ".":
                    continue
                stats["fetched"] += 1
                filas.append(
                    {
                        "series_id": series.id,
                        "obs_date": date.fromisoformat(obs["date"]),
                        "vintage_date": date.fromisoformat(
                            obs["realtime_start"]
                        ),
                        "value": float(val),
                    }
                )
            # Upsert por lotes (límite de 65535 parámetros de Postgres).
            for i in range(0, len(filas), 5000):
                chunk = filas[i : i + 5000]
                stmt = insert(DataPointVintage).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["series_id", "obs_date", "vintage_date"],
                    set_={"value": stmt.excluded.value},
                )
                session.execute(stmt)
            session.commit()
            stats["inserted"] = len(filas)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            stats["errors"] += 1
            logger.error("Error vintages FRED %s: %s", fred_id, e)
        finally:
            session.close()
        return stats

    def fetch_units(self) -> dict[str, str]:
        """Traer la unidad oficial de cada serie de FRED.

        El fetcher solo llamaba a `series/observations`, que devuelve
        los valores pero no su unidad, asi que los 65 indicadores de
        FRED quedaban con `unit` a NULL. `/fred/series` la da gratis, a
        una llamada por serie.
        """
        if not self.api_key:
            logger.error("STONKS_FRED_API_KEY no configurada")
            return {}

        session = get_session()
        aplicadas: dict[str, str] = {}
        try:
            for entrada in FRED_SERIES:
                code, fred_id = entrada[0], entrada[1]
                self._rate_limit()
                try:
                    datos = self._fred_get(
                        "series", {"series_id": fred_id}
                    )
                except Exception as e:  # noqa: BLE001
                    # Las series retiradas devuelven 400. Es un dato
                    # util, no un fallo: conviene saber cuales son.
                    logger.warning(
                        "FRED %s (%s) sin metadatos: %s", code, fred_id, e
                    )
                    continue

                bruto = (datos.get("seriess") or [{}])[0].get("units")
                unidad = normalizar_unidad(bruto)
                if not unidad:
                    continue

                ind = session.query(Indicator).filter_by(code=code).first()
                if ind is None:
                    continue
                ind.unit = unidad
                aplicadas[code] = unidad

            session.commit()
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.error("Error trayendo unidades de FRED: %s", e)
        finally:
            session.close()

        logger.info("FRED: unidad recuperada de %d series", len(aplicadas))
        return aplicadas

    def fetch_all_vintages(self) -> dict[str, dict]:
        """Descargar vintages ALFRED de todas las series clave."""
        if not self.api_key:
            logger.error("STONKS_FRED_API_KEY no configurada")
            return {}
        run_id = self._start_run(params={"type": "vintages"})
        results = {}
        total_ins = total_err = 0
        for code, fred_id in VINTAGE_SERIES:
            logger.info("ALFRED vintages: %s (%s)...", code, fred_id)
            stats = self.fetch_vintages(fred_id, code)
            results[code] = stats
            total_ins += stats["inserted"]
            total_err += stats["errors"]
            logger.info("  → %d vintages", stats["inserted"])
        self._finish_run(
            run_id,
            "success" if total_err == 0 else "partial",
            fetched=sum(r["fetched"] for r in results.values()),
            inserted=total_ins,
            errors=total_err,
        )
        return results

    def fetch_all(
        self,
        start_date: str = "2000-01-01",
    ) -> dict[str, dict]:
        """Descargar todas las series FRED."""
        if not self.api_key:
            logger.error("STONKS_FRED_API_KEY no configurada")
            return {}

        run_id = self._start_run(
            params={
                "type": "all_series",
                "start_date": start_date,
            }
        )
        results = {}
        total = len(FRED_SERIES)
        total_ins = 0
        total_err = 0

        for i, (code, fred_id, _desc, domain, _freq) in enumerate(
            FRED_SERIES, 1
        ):
            logger.info(
                "[%d/%d] FRED: %s (%s)...",
                i,
                total,
                code,
                fred_id,
            )
            stats = self.fetch_series(
                fred_id,
                code,
                domain=domain,
                start_date=start_date,
            )
            results[code] = stats
            total_ins += stats["inserted"]
            total_err += stats["errors"]
            logger.info("  → %d insertados", stats["inserted"])

        self._finish_run(
            run_id,
            "success" if total_err == 0 else "partial",
            fetched=sum(r["fetched"] for r in results.values()),
            inserted=total_ins,
            errors=total_err,
        )

        return results
