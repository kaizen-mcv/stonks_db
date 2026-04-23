"""Fetcher para FRED (Federal Reserve Economic Data)."""

from datetime import date, datetime

from sqlalchemy import and_

from stonks.config import settings
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
import stonks.models  # noqa: F401
from stonks.models.fixed_income import YieldCurve
from stonks.models.alternative import (
    SentimentIndicator,
    SentimentValue,
)
from stonks.models.macro import (
    DataPoint,
    Indicator,
    IndicatorSource,
    Series,
)
from stonks.models.meta import DataSource

# Series FRED con frecuencia mensual/diaria
# (code_interno, fred_series_id, descripcion,
#  dominio, frecuencia)
FRED_SERIES = [
    # Tipos de interés de bancos centrales
    ("FED_FUNDS_RATE", "FEDFUNDS",
     "Federal Funds Effective Rate",
     "macro", "monthly"),
    ("FED_FUNDS_UPPER", "DFEDTARU",
     "Fed Funds Upper Target",
     "macro", "daily"),
    ("ECB_MAIN_RATE", "ECBMRRFR",
     "ECB Main Refinancing Rate",
     "macro", "monthly"),
    ("BOJ_RATE", "IRSTCI01JPM156N",
     "Japan Short-Term Rate",
     "macro", "monthly"),
    ("BOE_RATE", "BOERUKM",
     "Bank of England Rate",
     "macro", "monthly"),
    # Inflación mensual US
    ("US_CPI_MOM", "CPIAUCSL",
     "US CPI Urban All Items",
     "macro", "monthly"),
    ("US_CORE_CPI", "CPILFESL",
     "US Core CPI (ex food/energy)",
     "macro", "monthly"),
    ("US_PCE", "PCEPI",
     "US PCE Price Index",
     "macro", "monthly"),
    ("US_CORE_PCE", "PCEPILFE",
     "US Core PCE (ex food/energy)",
     "macro", "monthly"),
    # Empleo mensual US
    ("US_UNEMPLOYMENT", "UNRATE",
     "US Unemployment Rate",
     "macro", "monthly"),
    ("US_NONFARM_PAYROLLS", "PAYEMS",
     "US Total Nonfarm Payrolls",
     "macro", "monthly"),
    ("US_INITIAL_CLAIMS", "ICSA",
     "US Initial Jobless Claims",
     "macro", "weekly"),
    # PIB trimestral US
    ("US_GDP_QUARTERLY", "GDP",
     "US GDP (nominal, quarterly)",
     "macro", "quarterly"),
    ("US_GDP_GROWTH", "A191RL1Q225SBEA",
     "US Real GDP Growth Rate",
     "macro", "quarterly"),
    # Producción / actividad
    ("US_INDUSTRIAL_PROD", "INDPRO",
     "US Industrial Production Index",
     "macro", "monthly"),
    ("US_CAPACITY_UTIL", "TCU",
     "US Capacity Utilization",
     "macro", "monthly"),
    ("US_PMI_MANUF", "MANEMP",
     "US Manufacturing Employment",
     "macro", "monthly"),
    # Vivienda
    ("US_HOUSING_STARTS", "HOUST",
     "US Housing Starts",
     "macro", "monthly"),
    ("US_EXISTING_HOME_SALES", "EXHOSLUSM495S",
     "US Existing Home Sales",
     "macro", "monthly"),
    ("CASE_SHILLER_US", "CSUSHPINSA",
     "S&P/Case-Shiller US Home Price",
     "alt", "monthly"),
    # Consumo / confianza
    ("US_RETAIL_SALES", "RSXFS",
     "US Advance Retail Sales",
     "macro", "monthly"),
    ("US_CONSUMER_SENTIMENT", "UMCSENT",
     "U Michigan Consumer Sentiment",
     "alt", "monthly"),
    # Yields diarios US Treasury
    ("UST_3M", "DGS3MO",
     "US Treasury 3-Month Yield",
     "fi", "daily"),
    ("UST_2Y", "DGS2",
     "US Treasury 2-Year Yield",
     "fi", "daily"),
    ("UST_5Y", "DGS5",
     "US Treasury 5-Year Yield",
     "fi", "daily"),
    ("UST_10Y", "DGS10",
     "US Treasury 10-Year Yield",
     "fi", "daily"),
    ("UST_30Y", "DGS30",
     "US Treasury 30-Year Yield",
     "fi", "daily"),
    # Spreads
    ("SPREAD_10Y2Y", "T10Y2Y",
     "10Y-2Y Treasury Spread",
     "fi", "daily"),
    ("SPREAD_10Y3M", "T10Y3M",
     "10Y-3M Treasury Spread",
     "fi", "daily"),
    ("HY_SPREAD", "BAMLH0A0HYM2",
     "ICE BofA US High Yield Spread",
     "fi", "daily"),
    ("IG_SPREAD", "BAMLC0A0CM",
     "ICE BofA US Corporate IG Spread",
     "fi", "daily"),
    # Otros yields internacionales
    ("DE_10Y", "IRLTLT01DEM156N",
     "Germany 10-Year Bond Yield",
     "fi", "monthly"),
    ("JP_10Y", "IRLTLT01JPM156N",
     "Japan 10-Year Bond Yield",
     "fi", "monthly"),
    ("GB_10Y", "IRLTLT01GBM156N",
     "UK 10-Year Bond Yield",
     "fi", "monthly"),
    # Oferta monetaria
    ("US_M2", "M2SL",
     "US M2 Money Stock",
     "macro", "monthly"),
    # Commodities (precio diario via FRED)
    ("GOLD_LONDON_FIX", "GOLDAMGBD228NLBM",
     "Gold Fixing Price London",
     "commodity", "daily"),
    ("OIL_WTI_SPOT", "DCOILWTICO",
     "Crude Oil WTI Spot Price",
     "commodity", "daily"),
    ("OIL_BRENT_SPOT", "DCOILBRENTEU",
     "Crude Oil Brent Spot Price",
     "commodity", "daily"),
    # Breakeven inflation
    ("BREAKEVEN_5Y", "T5YIE",
     "5-Year Breakeven Inflation",
     "fi", "daily"),
    ("BREAKEVEN_10Y", "T10YIE",
     "10-Year Breakeven Inflation",
     "fi", "daily"),
    # Tipo real
    ("REAL_RATE_10Y", "REAINTRATREARAT10Y",
     "10-Year Real Interest Rate",
     "fi", "monthly"),
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
            raise ValueError(
                "STONKS_FRED_API_KEY no configurada"
            )
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
            "fetched": 0, "inserted": 0,
            "updated": 0, "errors": 0,
        }
        session = get_session()

        try:
            src = session.query(DataSource).filter_by(
                name=self.SOURCE_NAME
            ).first()
            src_id = src.id if src else None

            data = self._fred_get(
                "series/observations",
                params={
                    "series_id": fred_id,
                    "observation_start": start_date,
                    "sort_order": "asc",
                },
            )

            observations = data.get(
                "observations", []
            )

            # Guardar según dominio
            if domain == "fi" and code in (
                YIELD_MATURITY
            ):
                # Yield curves
                maturity = YIELD_MATURITY[code]
                for obs in observations:
                    val = obs.get("value", ".")
                    if val == ".":
                        continue
                    stats["fetched"] += 1
                    dt = date.fromisoformat(
                        obs["date"]
                    )
                    exists = session.query(
                        YieldCurve
                    ).filter(and_(
                        YieldCurve.country_code
                        == "USA",
                        YieldCurve.date == dt,
                        YieldCurve.maturity_months
                        == maturity,
                    )).first()
                    if exists:
                        continue
                    session.add(YieldCurve(
                        country_code="USA",
                        date=dt,
                        maturity_months=maturity,
                        yield_pct=float(val),
                        source_id=src_id,
                    ))
                    stats["inserted"] += 1

            elif domain == "alt":
                # Sentimiento / housing
                ind = session.query(
                    SentimentIndicator
                ).filter_by(code=code).first()
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
                    dt = date.fromisoformat(
                        obs["date"]
                    )
                    exists = session.query(
                        SentimentValue
                    ).filter(and_(
                        SentimentValue.indicator_id
                        == ind.id,
                        SentimentValue.date == dt,
                    )).first()
                    if exists:
                        continue
                    session.add(SentimentValue(
                        indicator_id=ind.id,
                        date=dt,
                        value=float(val),
                    ))
                    stats["inserted"] += 1

            else:
                # Macro genérico → macro.data_point
                ind = session.query(
                    Indicator
                ).filter_by(code=code).first()
                if not ind:
                    # Buscar descripción
                    desc = code
                    for c, fid, d, _, _ in (
                        FRED_SERIES
                    ):
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

                series = session.query(
                    Series
                ).filter_by(
                    indicator_id=ind.id,
                    country_code="USA",
                    region_code=None,
                ).first()
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
                    dt = date.fromisoformat(
                        obs["date"]
                    )
                    exists = session.query(
                        DataPoint
                    ).filter(and_(
                        DataPoint.series_id
                        == series.id,
                        DataPoint.date == dt,
                    )).first()
                    if exists:
                        continue
                    session.add(DataPoint(
                        series_id=series.id,
                        date=dt,
                        value=float(val),
                        source_id=src_id,
                    ))
                    series.point_count += 1
                    stats["inserted"] += 1

                if series and observations:
                    last = [
                        o for o in observations
                        if o.get("value", ".") != "."
                    ]
                    if last:
                        series.last_date = (
                            date.fromisoformat(
                                last[-1]["date"]
                            )
                        )
                        series.last_value = float(
                            last[-1]["value"]
                        )

            session.commit()

        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error(
                "Error FRED %s: %s", fred_id, e
            )
        finally:
            session.close()

        return stats

    def fetch_all(
        self,
        start_date: str = "2000-01-01",
    ) -> dict[str, dict]:
        """Descargar todas las series FRED."""
        if not self.api_key:
            logger.error(
                "STONKS_FRED_API_KEY no configurada"
            )
            return {}

        run_id = self._start_run(params={
            "type": "all_series",
            "start_date": start_date,
        })
        results = {}
        total = len(FRED_SERIES)
        total_ins = 0
        total_err = 0

        for i, (code, fred_id, desc,
                 domain, freq) in enumerate(
            FRED_SERIES, 1
        ):
            logger.info(
                "[%d/%d] FRED: %s (%s)...",
                i, total, code, fred_id,
            )
            stats = self.fetch_series(
                fred_id, code, domain=domain,
                start_date=start_date,
            )
            results[code] = stats
            total_ins += stats["inserted"]
            total_err += stats["errors"]
            logger.info(
                "  → %d insertados", stats["inserted"]
            )

        self._finish_run(
            run_id,
            "success" if total_err == 0 else "partial",
            fetched=sum(
                r["fetched"] for r in results.values()
            ),
            inserted=total_ins,
            errors=total_err,
        )

        return results
