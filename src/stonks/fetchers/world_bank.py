"""Fetcher para World Bank Open Data API."""

from datetime import date

from sqlalchemy import and_

# Importar todos los modelos para resolver FKs
import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.macro import (
    DataPoint,
    Indicator,
    IndicatorSource,
    Series,
)
from stonks.models.meta import DataSource

# Top 20 economías por PIB + agregados
DEFAULT_COUNTRIES = [
    "USA",
    "CHN",
    "JPN",
    "DEU",
    "IND",
    "GBR",
    "FRA",
    "ITA",
    "BRA",
    "CAN",
    "RUS",
    "KOR",
    "AUS",
    "ESP",
    "MEX",
    "IDN",
    "NLD",
    "SAU",
    "TUR",
    "CHE",
]

# Regiones/agregados del World Bank
AGGREGATES = {
    "WLD": "World",
    "EUU": "European Union",
    "OED": "OECD members",
    "EAS": "East Asia & Pacific",
    "LCN": "Latin America & Caribbean",
    "SSF": "Sub-Saharan Africa",
    "SAS": "South Asia",
    "MEA": "Middle East & North Africa",
}


class WorldBankFetcher(BaseFetcher):
    """Descarga indicadores macro del World Bank."""

    SOURCE_NAME = "world_bank"
    DOMAIN = "macro"
    RATE_LIMIT = 0.2
    BASE_URL = "https://api.worldbank.org/v2"

    def fetch_indicator(
        self,
        indicator_code: str,
        countries: list[str] | None = None,
        date_range: str = "1960:2025",
    ) -> dict[str, int]:
        """Descargar un indicador para varios países.

        Returns:
            {"fetched": N, "inserted": N, "updated": N}
        """
        if countries is None:
            countries = DEFAULT_COUNTRIES

        run_id = self._start_run(
            params={
                "indicator": indicator_code,
                "countries": countries,
                "date_range": date_range,
            }
        )

        session = get_session()
        stats = {
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
        }

        try:
            # Buscar indicador y source_id
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            if not src:
                raise ValueError("Fuente world_bank no encontrada")

            ind_src = (
                session.query(IndicatorSource)
                .filter_by(
                    source_id=src.id,
                    external_code=indicator_code,
                )
                .first()
            )

            if not ind_src:
                # Buscar por código del indicador
                ind = (
                    session.query(Indicator)
                    .filter(
                        Indicator.id == IndicatorSource.indicator_id,
                        IndicatorSource.external_code == indicator_code,
                    )
                    .first()
                )
                if not ind:
                    logger.warning(
                        "Indicador %s no registrado",
                        indicator_code,
                    )
                    self._finish_run(
                        run_id,
                        "failed",
                        error_log={"msg": "Indicador no registrado"},
                    )
                    session.close()
                    return stats
                indicator_id = ind.id
            else:
                indicator_id = ind_src.indicator_id

            # Descargar por bloques de países
            country_str = ";".join(countries)
            page = 1
            total_pages = 1

            while page <= total_pages:
                url = (
                    f"{self.BASE_URL}/country/"
                    f"{country_str}/indicator/"
                    f"{indicator_code}"
                )
                params = {
                    "format": "json",
                    "date": date_range,
                    "per_page": 1000,
                    "page": page,
                }

                data = self._get(url, params)

                if not data or len(data) < 2 or not data[1]:
                    break

                meta_info = data[0]
                total_pages = meta_info.get("pages", 1)
                records = data[1]

                for rec in records:
                    val = rec.get("value")
                    if val is None:
                        continue

                    stats["fetched"] += 1
                    country_code = rec["countryiso3code"]
                    year = int(rec["date"])
                    dt = date(year, 12, 31)

                    # Obtener o crear serie
                    series = (
                        session.query(Series)
                        .filter_by(
                            indicator_id=indicator_id,
                            country_code=country_code,
                            region_code=None,
                        )
                        .first()
                    )

                    if not series:
                        series = Series(
                            indicator_id=indicator_id,
                            country_code=country_code,
                            point_count=0,
                        )
                        session.add(series)
                        session.flush()

                    # Insertar o actualizar punto
                    existing = (
                        session.query(DataPoint)
                        .filter(
                            and_(
                                DataPoint.series_id == series.id,
                                DataPoint.date == dt,
                            )
                        )
                        .first()
                    )

                    if existing:
                        if float(existing.value) != (float(val)):
                            existing.value = val
                            existing.source_id = src.id
                            stats["updated"] += 1
                    else:
                        session.add(
                            DataPoint(
                                series_id=series.id,
                                date=dt,
                                value=val,
                                source_id=src.id,
                            )
                        )
                        series.point_count += 1
                        stats["inserted"] += 1

                    # Actualizar último valor
                    if series.last_date is None or dt > series.last_date:
                        series.last_date = dt
                        series.last_value = val

                page += 1

            session.commit()
            self._finish_run(run_id, "success", **stats)

        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error(
                "Error descargando %s: %s",
                indicator_code,
                e,
            )
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats

    def fetch_all_indicators(
        self,
        countries: list[str] | None = None,
    ) -> dict[str, dict]:
        """Descargar todos los indicadores
        configurados."""
        session = get_session()
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            logger.error("Fuente world_bank no encontrada")
            session.close()
            return {}

        ind_sources = (
            session.query(IndicatorSource).filter_by(source_id=src.id).all()
        )
        session.close()

        results = {}
        for isrc in ind_sources:
            code = isrc.external_code
            logger.info("Descargando indicador: %s", code)
            results[code] = self.fetch_indicator(code, countries=countries)
            logger.info(
                "  → fetched=%d inserted=%d updated=%d",
                results[code]["fetched"],
                results[code]["inserted"],
                results[code]["updated"],
            )

        return results
