"""Fetcher de perfiles de país desde World Bank."""

from datetime import datetime

import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.country import (
    CountryProfile,
    Demographics,
)

# Países principales para perfiles
PROFILE_COUNTRIES = [
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
    "POL",
    "SWE",
    "NOR",
    "DNK",
    "FIN",
    "IRL",
    "SGP",
    "HKG",
    "ISR",
    "ARE",
    "NZL",
    "PRT",
    "GRC",
    "CZE",
    "HUN",
    "CHL",
    "COL",
    "ARG",
    "PER",
    "ZAF",
]

# Indicadores para perfil de país
PROFILE_INDICATORS = {
    "SP.POP.TOTL": "population",
    "NY.GDP.MKTP.CD": "gdp_usd",
    "NY.GDP.PCAP.CD": "gdp_per_capita_usd",
    "SI.POV.GINI": "gini_index",
}

DEMO_INDICATORS = {
    "SP.POP.TOTL": "total_population",
    "SP.URB.TOTL.IN.ZS": "urban_population_pct",
    "SP.DYN.LE00.IN": "life_expectancy",
    "SP.DYN.TFRT.IN": "fertility_rate",
    "SL.TLF.TOTL.IN": "labor_force",
}


class CountryProfileFetcher(BaseFetcher):
    """Descarga perfiles de país desde World Bank."""

    SOURCE_NAME = "world_bank"
    DOMAIN = "country"
    RATE_LIMIT = 0.2
    BASE_URL = "https://api.worldbank.org/v2"

    @staticmethod
    def _paises_objetivo(session) -> list[str]:
        """Codigos ISO3 para los que pedir perfil.

        Se toman de `ref.country`; si por lo que sea el catalogo esta
        vacio, se cae a la lista fija historica para no quedarse sin
        hacer nada.
        """
        from sqlalchemy import text

        # Solo los que el World Bank reconoce. `ref.country` incluye
        # territorios sin estadisticas (Antartida, Isla Bouvet...) y
        # basta con que uno sea invalido para que la API rechace el
        # lote entero de 20, tumbando a los 19 buenos con el.
        filas = session.execute(
            text(
                "SELECT DISTINCT s.country_code FROM macro.series s "
                "JOIN macro.indicator i ON i.id = s.indicator_id "
                "WHERE i.code = 'GDP_NOMINAL' "
                "AND s.country_code IS NOT NULL "
                "ORDER BY 1"
            )
        ).fetchall()
        return [f[0] for f in filas] or list(PROFILE_COUNTRIES)

    def fetch_profiles(self) -> dict[str, int]:
        """Descargar perfiles de país (último dato)."""
        run_id = self._start_run(
            params={
                "type": "profiles",
            }
        )
        stats = {
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
        }
        session = get_session()

        try:
            # Antes se usaba PROFILE_COUNTRIES, una lista fija de 40
            # paises: por eso country.profile tenia 40 filas de 250.
            # Se recorre el catalogo entero de ref.country.
            paises = self._paises_objetivo(session)
            logger.info("  Perfiles de %d paises", len(paises))
            # World Bank acepta max ~20 países
            chunks = [
                paises[i : i + 20] for i in range(0, len(paises), 20)
            ]
            for indicator_code, field in PROFILE_INDICATORS.items():
                logger.info("  Perfil: %s...", indicator_code)
                for chunk in chunks:
                    country_str = ";".join(chunk)
                    url = (
                        f"{self.BASE_URL}/country/"
                        f"{country_str}/indicator/"
                        f"{indicator_code}"
                    )
                    params = {
                        "format": "json",
                        "date": "2020:2025",
                        "per_page": 500,
                    }

                    try:
                        data = self._get(url, params)
                    except Exception as e:
                        logger.warning(
                            "  Error %s: %s",
                            indicator_code,
                            e,
                        )
                        stats["errors"] += 1
                        continue

                    if not data or len(data) < 2:
                        continue

                    records = data[1] or []
                    for rec in records:
                        val = rec.get("value")
                        if val is None:
                            continue

                        stats["fetched"] += 1
                        cc = rec["countryiso3code"]

                        profile = (
                            session.query(CountryProfile)
                            .filter_by(country_code=cc)
                            .first()
                        )

                        if not profile:
                            profile = CountryProfile(
                                country_code=cc,
                                last_updated=(datetime.now()),
                            )
                            session.add(profile)
                            stats["inserted"] += 1
                        else:
                            stats["updated"] += 1

                        setattr(profile, field, val)
                        if field == "population":
                            profile.population_year = int(rec["date"])
                        profile.last_updated = datetime.now()

            session.commit()
            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error profiles: %s", e)
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats

    def fetch_demographics(
        self,
        date_range: str = "2000:2025",
    ) -> dict[str, int]:
        """Descargar demografía histórica."""
        run_id = self._start_run(
            params={
                "type": "demographics",
                "date_range": date_range,
            }
        )
        stats = {
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
        }
        session = get_session()

        try:
            chunks = [
                PROFILE_COUNTRIES[i : i + 20]
                for i in range(0, len(PROFILE_COUNTRIES), 20)
            ]

            for indicator_code, field in DEMO_INDICATORS.items():
                logger.info(
                    "  Demografía: %s...",
                    indicator_code,
                )
                all_records = []
                for chunk in chunks:
                    country_str = ";".join(chunk)
                    url = (
                        f"{self.BASE_URL}/country/"
                        f"{country_str}/indicator/"
                        f"{indicator_code}"
                    )
                    params = {
                        "format": "json",
                        "date": date_range,
                        "per_page": 1000,
                    }

                    try:
                        data = self._get(url, params)
                    except Exception:
                        stats["errors"] += 1
                        continue

                    if data and len(data) >= 2:
                        all_records.extend(data[1] or [])

                records = all_records
                for rec in records:
                    val = rec.get("value")
                    if val is None:
                        continue

                    stats["fetched"] += 1
                    cc = rec["countryiso3code"]
                    year = int(rec["date"])

                    demo = (
                        session.query(Demographics)
                        .filter_by(
                            country_code=cc,
                            year=year,
                        )
                        .first()
                    )

                    if not demo:
                        demo = Demographics(
                            country_code=cc,
                            year=year,
                        )
                        session.add(demo)
                        stats["inserted"] += 1

                    setattr(demo, field, val)

                session.commit()

            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error demographics: %s", e)
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats
