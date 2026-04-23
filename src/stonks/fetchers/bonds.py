"""Fetcher de bonos soberanos y ratings crediticios."""

import csv
import io
from datetime import date, datetime

from sqlalchemy import and_

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
import stonks.models  # noqa: F401
from stonks.models.fixed_income import (
    Bond,
    BondIssuer,
    CreditRating,
)
from stonks.models.meta import DataSource

# Emisores soberanos G20+ principales
GOVERNMENT_ISSUERS = [
    ("US Department of the Treasury", "USA"),
    ("HM Treasury", "GBR"),
    ("Agence France Trésor", "FRA"),
    ("German Federal Government", "DEU"),
    ("Italian Treasury", "ITA"),
    ("Spanish Treasury", "ESP"),
    ("Japanese Ministry of Finance", "JPN"),
    ("People's Republic of China", "CHN"),
    ("Reserve Bank of India", "IND"),
    ("Brazilian National Treasury", "BRA"),
    ("Bank of Canada", "CAN"),
    ("Australian Government", "AUS"),
    ("Russian Federation", "RUS"),
    ("Republic of Korea", "KOR"),
    ("Republic of Indonesia", "IDN"),
    ("Republic of Mexico", "MEX"),
    ("Republic of Turkey", "TUR"),
    ("Kingdom of Saudi Arabia", "SAU"),
    ("Republic of South Africa", "ZAF"),
    ("Argentine Republic", "ARG"),
    ("Kingdom of the Netherlands", "NLD"),
    ("Kingdom of Belgium", "BEL"),
    ("Swiss Confederation", "CHE"),
    ("Kingdom of Sweden", "SWE"),
    ("Kingdom of Norway", "NOR"),
    ("Kingdom of Denmark", "DNK"),
    ("Republic of Poland", "POL"),
    ("Republic of Portugal", "PRT"),
    ("Republic of Ireland", "IRL"),
    ("Hellenic Republic", "GRC"),
]

# Mapeo pais (issuer_name en CSV) -> country_code
# para vincular ratings con issuers
COUNTRY_RATING_MAP = {
    "United States of America": "USA",
    "United States": "USA",
    "United Kingdom": "GBR",
    "France": "FRA",
    "Germany": "DEU",
    "Italy": "ITA",
    "Spain": "ESP",
    "Japan": "JPN",
    "China": "CHN",
    "India": "IND",
    "Brazil": "BRA",
    "Canada": "CAN",
    "Australia": "AUS",
    "Russia": "RUS",
    "Korea": "KOR",
    "South Korea": "KOR",
    "Indonesia": "IDN",
    "Mexico": "MEX",
    "Turkey": "TUR",
    "Turkiye": "TUR",
    "Saudi Arabia": "SAU",
    "South Africa": "ZAF",
    "Argentina": "ARG",
    "Netherlands": "NLD",
    "Belgium": "BEL",
    "Switzerland": "CHE",
    "Sweden": "SWE",
    "Norway": "NOR",
    "Denmark": "DNK",
    "Poland": "POL",
    "Portugal": "PRT",
    "Ireland": "IRL",
    "Greece": "GRC",
    "Nigeria": "NGA",
    "Colombia": "COL",
    "Chile": "CHL",
    "Peru": "PER",
    "Egypt": "EGY",
    "Israel": "ISR",
    "Philippines": "PHL",
    "Thailand": "THA",
    "Malaysia": "MYS",
    "Vietnam": "VNM",
    "New Zealand": "NZL",
    "Austria": "AUT",
    "Finland": "FIN",
    "Czech Republic": "CZE",
    "Romania": "ROU",
    "Hungary": "HUN",
    "Croatia": "HRV",
    "Singapore": "SGP",
    "Taiwan": "TWN",
    "Pakistan": "PAK",
    "Bangladesh": "BGD",
    "Kenya": "KEN",
    "Morocco": "MAR",
    "Ghana": "GHA",
    "Ukraine": "UKR",
}

# Tipos de bono segun security_type de Treasury
BOND_TYPE_MAP = {
    "Bond": "government_bond",
    "Note": "treasury_note",
    "Bill": "treasury_bill",
    "FRN": "floating_rate_note",
    "TIPS": "inflation_linked",
    "CMB": "cash_management_bill",
}

# Frecuencia de pago segun tipo
COUPON_FREQ_MAP = {
    "Semi-Annual": 2,
    "Quarterly": 4,
    "Annual": 1,
    "None": 0,
}

TREASURY_API = (
    "https://api.fiscaldata.treasury.gov"
    "/services/api/fiscal_service"
    "/v1/accounting/od/auctions_query"
)

FITCH_SOVEREIGN_URL = (
    "https://ratingshistory.info/api/public/"
    "20260401%20Fitch%20Ratings%20Sovereign.csv"
)


class BondFetcher(BaseFetcher):
    """Fetcher de bonos soberanos y ratings."""

    SOURCE_NAME = "treasury_fiscal"
    DOMAIN = "fi"
    RATE_LIMIT = 0.5

    def seed_government_issuers(
        self,
    ) -> dict[str, int]:
        """Insertar emisores soberanos G20+."""
        stats = {"inserted": 0, "errors": 0}
        session = get_session()

        try:
            for name, country in GOVERNMENT_ISSUERS:
                exists = (
                    session.query(BondIssuer)
                    .filter(
                        and_(
                            BondIssuer.name == name,
                            BondIssuer.country_code
                            == country,
                            BondIssuer.issuer_type
                            == "government",
                        )
                    )
                    .first()
                )
                if exists:
                    continue

                session.add(
                    BondIssuer(
                        name=name,
                        country_code=country,
                        issuer_type="government",
                    )
                )
                stats["inserted"] += 1

            session.commit()
            logger.info(
                "Emisores soberanos insertados: %d",
                stats["inserted"],
            )
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error(
                "Error seed issuers: %s", e
            )
        finally:
            session.close()

        return stats

    def fetch_us_bonds(self) -> dict[str, int]:
        """Descargar bonos US Treasury via API."""
        run_id = self._start_run(
            params={"type": "us_bonds"}
        )
        stats = {
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
        }

        # Estado incremental
        state = self._load_state("us_bonds")
        last_date = state.get("last_auction_date")

        session = get_session()

        try:
            # Buscar issuer US Treasury
            us_issuer = (
                session.query(BondIssuer)
                .filter_by(country_code="USA")
                .first()
            )
            if not us_issuer:
                logger.error(
                    "No existe issuer USA. "
                    "Ejecuta 'stonks fi seed' primero."
                )
                self._finish_run(
                    run_id, "failed", **stats
                )
                return stats

            issuer_id = us_issuer.id
            page = 1
            max_date = last_date or ""

            while True:
                params = {
                    "page[number]": page,
                    "page[size]": 1000,
                    "sort": "-auction_date",
                }
                if last_date:
                    params["filter"] = (
                        f"auction_date:gte:"
                        f"{last_date}"
                    )

                data = self._get(
                    TREASURY_API, params=params
                )
                records = data.get("data", [])

                if not records:
                    break

                for rec in records:
                    stats["fetched"] += 1
                    cusip = rec.get("cusip", "")
                    if not cusip or cusip == "null":
                        continue

                    sec_type = rec.get(
                        "security_type", ""
                    )
                    bond_type = BOND_TYPE_MAP.get(
                        sec_type, "government_bond"
                    )

                    # Nombre del bono
                    term = rec.get(
                        "security_term", ""
                    )
                    name = (
                        f"US Treasury {sec_type} "
                        f"{term} {cusip}"
                    )

                    # Coupon
                    int_rate = rec.get("int_rate")
                    coupon = _safe_float(int_rate)

                    # Frecuencia
                    freq_str = rec.get(
                        "int_payment_frequency",
                        "None",
                    )
                    coupon_freq = COUPON_FREQ_MAP.get(
                        freq_str, 0
                    )

                    # Fechas
                    issue = _safe_date(
                        rec.get("issue_date")
                    )
                    maturity = _safe_date(
                        rec.get("maturity_date")
                    )
                    auction = rec.get(
                        "auction_date", ""
                    )

                    # Callable
                    is_callable = (
                        rec.get("callable") == "Yes"
                    )

                    # Verificar duplicado
                    exists = (
                        session.query(Bond)
                        .filter_by(isin=cusip)
                        .first()
                    )
                    if exists:
                        continue

                    session.add(
                        Bond(
                            issuer_id=issuer_id,
                            isin=cusip[:12],
                            name=name[:300],
                            coupon_rate=coupon,
                            coupon_frequency=coupon_freq,
                            maturity_date=maturity,
                            issue_date=issue,
                            face_value=1000.00,
                            currency_code="USD",
                            bond_type=bond_type,
                            is_callable=is_callable,
                        )
                    )
                    stats["inserted"] += 1

                    if auction and auction > max_date:
                        max_date = auction

                session.commit()
                logger.info(
                    "  Pagina %d: %d registros",
                    page,
                    len(records),
                )

                # Siguiente pagina
                meta = data.get("meta", {})
                total_pages = meta.get(
                    "total-pages", 1
                )
                if page >= total_pages:
                    break
                page += 1

            # Guardar estado
            if max_date:
                self._save_state(
                    "us_bonds",
                    {"last_auction_date": max_date},
                )

            self._finish_run(
                run_id, "success", **stats
            )
            logger.info(
                "Bonos US importados: %d",
                stats["inserted"],
            )

        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error(
                "Error fetch US bonds: %s", e
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

    def fetch_sovereign_ratings(
        self,
    ) -> dict[str, int]:
        """Descargar ratings soberanos de Fitch."""
        run_id = self._start_run(
            params={"type": "sovereign_ratings"}
        )
        stats = {
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
        }

        # Estado incremental
        state = self._load_state("ratings")
        last_date = state.get("last_date")

        session = get_session()

        try:
            # Cache de issuers por country_code
            issuer_cache = {}
            for issuer in (
                session.query(BondIssuer)
                .filter_by(issuer_type="government")
                .all()
            ):
                issuer_cache[
                    issuer.country_code
                ] = issuer.id

            # Descargar CSV
            logger.info(
                "Descargando ratings Fitch "
                "Sovereign..."
            )
            self._rate_limit()
            resp = self._session.get(
                FITCH_SOVEREIGN_URL, timeout=60
            )
            resp.raise_for_status()

            # Parsear CSV
            text = resp.text
            reader = csv.DictReader(
                io.StringIO(text)
            )

            max_date = last_date or ""

            for row in reader:
                stats["fetched"] += 1

                # Solo Long Term ratings
                rating_type = row.get(
                    "rating_type", ""
                )
                if "Long Term" not in rating_type:
                    continue

                issuer_name = row.get(
                    "issuer_name", ""
                ).strip().strip('"')
                rating = row.get(
                    "rating", ""
                ).strip()
                rating_date_str = row.get(
                    "rating_action_date", ""
                ).strip()
                outlook = row.get(
                    "rating_outlook", ""
                ).strip() or None

                if (
                    not issuer_name
                    or not rating
                    or not rating_date_str
                ):
                    continue

                # Filtro incremental
                if (
                    last_date
                    and rating_date_str <= last_date
                ):
                    continue

                # Buscar country_code
                country = COUNTRY_RATING_MAP.get(
                    issuer_name
                )
                if not country:
                    continue

                issuer_id = issuer_cache.get(country)
                if not issuer_id:
                    # Crear issuer si no existe
                    new_issuer = BondIssuer(
                        name=issuer_name,
                        country_code=country,
                        issuer_type="government",
                    )
                    session.add(new_issuer)
                    session.flush()
                    issuer_id = new_issuer.id
                    issuer_cache[country] = issuer_id

                rating_date = _safe_date(
                    rating_date_str
                )
                if not rating_date:
                    continue

                # Check duplicado
                exists = (
                    session.query(CreditRating)
                    .filter(
                        and_(
                            CreditRating.issuer_id
                            == issuer_id,
                            CreditRating.agency
                            == "Fitch",
                            CreditRating.rating_date
                            == rating_date,
                        )
                    )
                    .first()
                )
                if exists:
                    continue

                session.add(
                    CreditRating(
                        issuer_id=issuer_id,
                        agency="Fitch",
                        rating=rating[:10],
                        outlook=outlook[:20]
                        if outlook
                        else None,
                        rating_date=rating_date,
                    )
                )
                stats["inserted"] += 1

                if (
                    rating_date_str > max_date
                ):
                    max_date = rating_date_str

            session.commit()

            # Guardar estado
            if max_date:
                self._save_state(
                    "ratings",
                    {"last_date": max_date},
                )

            self._finish_run(
                run_id, "success", **stats
            )
            logger.info(
                "Ratings soberanos insertados: %d",
                stats["inserted"],
            )

        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error(
                "Error fetch ratings: %s", e
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


def _safe_float(value: str | None) -> float | None:
    """Convertir string a float o None."""
    if not value or value.strip() in ("", "null"):
        return None
    try:
        return float(value.strip())
    except (ValueError, TypeError):
        return None


def _safe_date(value: str | None) -> date | None:
    """Convertir string YYYY-MM-DD a date."""
    if not value or value.strip() in ("", "null"):
        return None
    try:
        return datetime.strptime(
            value.strip()[:10], "%Y-%m-%d"
        ).date()
    except (ValueError, TypeError):
        return None
