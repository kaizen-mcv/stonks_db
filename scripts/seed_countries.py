"""Cargar países y divisas desde pycountry."""

import pycountry

from stonks.db import get_session, init_db
from stonks.logger import setup_logger
from stonks.models.ref import Country, Currency

logger = setup_logger("stonks.seed")

# Divisas principales
MAJOR_CURRENCIES = {
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "CAD",
    "AUD",
    "NZD",
    "CNY",
    "HKD",
    "SGD",
    "SEK",
    "NOK",
    "DKK",
    "KRW",
}


def seed_currencies() -> int:
    """Cargar divisas desde pycountry."""
    session = get_session()
    count = 0
    try:
        for cur in pycountry.currencies:
            exists = (
                session.query(Currency).filter_by(code=cur.alpha_3).first()
            )
            if exists:
                continue
            session.add(
                Currency(
                    code=cur.alpha_3,
                    name=cur.name,
                    is_major=cur.alpha_3 in MAJOR_CURRENCIES,
                )
            )
            count += 1
        session.commit()
    finally:
        session.close()
    return count


def seed_countries() -> int:
    """Cargar países desde pycountry."""
    session = get_session()
    count = 0
    try:
        for c in pycountry.countries:
            alpha3 = c.alpha_3
            exists = session.query(Country).filter_by(code=alpha3).first()
            if exists:
                continue
            session.add(
                Country(
                    code=alpha3,
                    code_alpha2=getattr(c, "alpha_2", None),
                    name=c.name,
                )
            )
            count += 1
        session.commit()
    finally:
        session.close()
    return count


def main() -> None:
    init_db()
    n_cur = seed_currencies()
    logger.info("Divisas cargadas: %d", n_cur)
    n_countries = seed_countries()
    logger.info("Países cargados: %d", n_countries)


if __name__ == "__main__":
    main()
