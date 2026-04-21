"""Seed de datos de referencia: países, divisas,
bolsas, sectores, fuentes, indicadores."""

from pathlib import Path

import pycountry
import yaml

from stonks.db import get_session
from stonks.logger import get_logger
from stonks.models.macro import Indicator, IndicatorSource
from stonks.models.meta import DataSource
from stonks.models.ref import Country, Currency, Exchange, Sector

logger = get_logger("stonks.seed")

CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"

# Divisas principales
MAJOR_CURRENCIES = {
    "USD", "EUR", "GBP", "JPY", "CHF",
    "CAD", "AUD", "NZD", "CNY", "HKD",
    "SGD", "SEK", "NOK", "DKK", "KRW",
}

# Bolsas principales (mic, short, name, country,
# city, tz, currency)
EXCHANGES = [
    ("XNYS", "NYSE", "New York Stock Exchange",
     "USA", "New York", "America/New_York", "USD"),
    ("XNAS", "NASDAQ", "NASDAQ",
     "USA", "New York", "America/New_York", "USD"),
    ("XLON", "LSE", "London Stock Exchange",
     "GBR", "London", "Europe/London", "GBP"),
    ("XETR", "XETRA", "Deutsche Börse XETRA",
     "DEU", "Frankfurt", "Europe/Berlin", "EUR"),
    ("XPAR", "Euronext Paris", "Euronext Paris",
     "FRA", "Paris", "Europe/Paris", "EUR"),
    ("XAMS", "Euronext AMS", "Euronext Amsterdam",
     "NLD", "Amsterdam", "Europe/Amsterdam", "EUR"),
    ("XBRU", "Euronext BRU", "Euronext Brussels",
     "BEL", "Brussels", "Europe/Brussels", "EUR"),
    ("XLIS", "Euronext LIS", "Euronext Lisbon",
     "PRT", "Lisbon", "Europe/Lisbon", "EUR"),
    ("XMIL", "Borsa Italiana", "Borsa Italiana",
     "ITA", "Milan", "Europe/Rome", "EUR"),
    ("XMAD", "BME", "Bolsa de Madrid",
     "ESP", "Madrid", "Europe/Madrid", "EUR"),
    ("XSWX", "SIX", "SIX Swiss Exchange",
     "CHE", "Zurich", "Europe/Zurich", "CHF"),
    ("XTSE", "TSX", "Toronto Stock Exchange",
     "CAN", "Toronto", "America/Toronto", "CAD"),
    ("XTKS", "TSE", "Tokyo Stock Exchange",
     "JPN", "Tokyo", "Asia/Tokyo", "JPY"),
    ("XHKG", "HKEX", "Hong Kong Stock Exchange",
     "HKG", "Hong Kong", "Asia/Hong_Kong", "HKD"),
    ("XSHG", "SSE", "Shanghai Stock Exchange",
     "CHN", "Shanghai", "Asia/Shanghai", "CNY"),
    ("XSHE", "SZSE", "Shenzhen Stock Exchange",
     "CHN", "Shenzhen", "Asia/Shanghai", "CNY"),
    ("XKRX", "KRX", "Korea Exchange",
     "KOR", "Seoul", "Asia/Seoul", "KRW"),
    ("XBOM", "BSE", "Bombay Stock Exchange",
     "IND", "Mumbai", "Asia/Kolkata", "INR"),
    ("XNSE", "NSE India", "National Stock Exchange",
     "IND", "Mumbai", "Asia/Kolkata", "INR"),
    ("XASX", "ASX", "Australian Securities Exchange",
     "AUS", "Sydney", "Australia/Sydney", "AUD"),
    ("XBSP", "B3", "B3 Brasil Bolsa Balcão",
     "BRA", "São Paulo", "America/Sao_Paulo", "BRL"),
    ("XMEX", "BMV", "Bolsa Mexicana de Valores",
     "MEX", "Mexico City", "America/Mexico_City",
     "MXN"),
    ("XJSE", "JSE", "Johannesburg Stock Exchange",
     "ZAF", "Johannesburg", "Africa/Johannesburg",
     "ZAR"),
    ("XSTO", "OMX Sthlm", "Nasdaq Stockholm",
     "SWE", "Stockholm", "Europe/Stockholm", "SEK"),
    ("XHEL", "OMX Hlsnk", "Nasdaq Helsinki",
     "FIN", "Helsinki", "Europe/Helsinki", "EUR"),
    ("XOSL", "Oslo Børs", "Oslo Stock Exchange",
     "NOR", "Oslo", "Europe/Oslo", "NOK"),
    ("XCSE", "OMX Cph", "Nasdaq Copenhagen",
     "DNK", "Copenhagen", "Europe/Copenhagen",
     "DKK"),
    ("XWAR", "GPW", "Warsaw Stock Exchange",
     "POL", "Warsaw", "Europe/Warsaw", "PLN"),
    ("XIST", "BIST", "Borsa Istanbul",
     "TUR", "Istanbul", "Europe/Istanbul", "TRY"),
    ("XTAE", "TASE", "Tel Aviv Stock Exchange",
     "ISR", "Tel Aviv", "Asia/Jerusalem", "ILS"),
    ("XSAU", "Tadawul", "Saudi Stock Exchange",
     "SAU", "Riyadh", "Asia/Riyadh", "SAR"),
    ("XSES", "SGX", "Singapore Exchange",
     "SGP", "Singapore", "Asia/Singapore", "SGD"),
    ("XIDX", "IDX", "Indonesia Stock Exchange",
     "IDN", "Jakarta", "Asia/Jakarta", "IDR"),
    ("XBKK", "SET", "Stock Exchange of Thailand",
     "THA", "Bangkok", "Asia/Bangkok", "THB"),
    ("XKLS", "Bursa MY", "Bursa Malaysia",
     "MYS", "Kuala Lumpur", "Asia/Kuala_Lumpur",
     "MYR"),
]

# GICS: (code, name, parent_code, level)
GICS = [
    ("10", "Energy", None, 1),
    ("15", "Materials", None, 1),
    ("20", "Industrials", None, 1),
    ("25", "Consumer Discretionary", None, 1),
    ("30", "Consumer Staples", None, 1),
    ("35", "Health Care", None, 1),
    ("40", "Financials", None, 1),
    ("45", "Information Technology", None, 1),
    ("50", "Communication Services", None, 1),
    ("55", "Utilities", None, 1),
    ("60", "Real Estate", None, 1),
    ("1010", "Energy", "10", 2),
    ("1510", "Materials", "15", 2),
    ("2010", "Capital Goods", "20", 2),
    ("2020", "Commercial & Prof. Services", "20", 2),
    ("2030", "Transportation", "20", 2),
    ("2510", "Automobiles & Components", "25", 2),
    ("2520", "Consumer Durables & Apparel", "25", 2),
    ("2530", "Consumer Services", "25", 2),
    ("2550", "Retailing", "25", 2),
    ("3010", "Food & Staples Retailing", "30", 2),
    ("3020", "Food Beverage & Tobacco", "30", 2),
    ("3030", "Household & Personal Products",
     "30", 2),
    ("3510", "HC Equipment & Services", "35", 2),
    ("3520", "Pharma Biotech & Life Sci", "35", 2),
    ("4010", "Banks", "40", 2),
    ("4020", "Financial Services", "40", 2),
    ("4030", "Insurance", "40", 2),
    ("4510", "Software & Services", "45", 2),
    ("4520", "Tech Hardware & Equipment", "45", 2),
    ("4530", "Semiconductors & Equipment", "45", 2),
    ("5010", "Telecom Services", "50", 2),
    ("5020", "Media & Entertainment", "50", 2),
    ("5510", "Utilities", "55", 2),
    ("6010", "Equity REITs", "60", 2),
    ("6020", "RE Mgmt & Development", "60", 2),
]


def seed_sources() -> int:
    """Cargar fuentes desde sources.yml."""
    yml = CONFIG_DIR / "sources.yml"
    with open(yml, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    session = get_session()
    count = 0
    try:
        for name, info in data.items():
            if session.query(DataSource).filter_by(
                name=name
            ).first():
                continue
            session.add(DataSource(
                name=name,
                display_name=info.get("display_name"),
                base_url=info.get("base_url"),
                api_key_env_var=info.get("api_key_env"),
                rate_limit_per_second=info.get(
                    "rate_limit"
                ),
                daily_request_limit=info.get(
                    "daily_limit"
                ),
                is_enabled=info.get("enabled", True),
            ))
            count += 1
        session.commit()
    finally:
        session.close()
    return count


def seed_currencies() -> int:
    """Cargar divisas desde pycountry."""
    session = get_session()
    count = 0
    try:
        for cur in pycountry.currencies:
            if session.query(Currency).filter_by(
                code=cur.alpha_3
            ).first():
                continue
            session.add(Currency(
                code=cur.alpha_3,
                name=cur.name,
                is_major=(
                    cur.alpha_3 in MAJOR_CURRENCIES
                ),
            ))
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
            if session.query(Country).filter_by(
                code=c.alpha_3
            ).first():
                continue
            session.add(Country(
                code=c.alpha_3,
                code_alpha2=getattr(
                    c, "alpha_2", None
                ),
                name=c.name,
            ))
            count += 1
        session.commit()
    finally:
        session.close()
    return count


def seed_exchanges() -> int:
    """Cargar bolsas principales."""
    session = get_session()
    count = 0
    try:
        for (mic, short, name, country,
             city, tz, currency) in EXCHANGES:
            if session.query(Exchange).filter_by(
                mic=mic
            ).first():
                continue
            session.add(Exchange(
                mic=mic,
                short_name=short,
                name=name,
                country_code=country,
                city=city,
                timezone=tz,
                currency_code=currency,
            ))
            count += 1
        session.commit()
    finally:
        session.close()
    return count


def seed_sectors() -> int:
    """Cargar sectores GICS."""
    session = get_session()
    count = 0
    code_to_id: dict[str, int] = {}
    try:
        for gics_code, name, parent_code, level in GICS:
            existing = session.query(Sector).filter_by(
                gics_code=gics_code
            ).first()
            if existing:
                code_to_id[gics_code] = existing.id
                continue
            parent_id = (
                code_to_id.get(parent_code)
                if parent_code else None
            )
            sector = Sector(
                gics_code=gics_code,
                name=name,
                parent_id=parent_id,
                level=level,
            )
            session.add(sector)
            session.flush()
            code_to_id[gics_code] = sector.id
            count += 1
        session.commit()
    finally:
        session.close()
    return count


def seed_indicators() -> int:
    """Cargar indicadores desde indicators.yml."""
    yml = CONFIG_DIR / "indicators.yml"
    with open(yml, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    session = get_session()
    count = 0
    try:
        source_cache: dict[str, int] = {}
        for src in session.query(DataSource).all():
            source_cache[src.name] = src.id

        for code, info in data.items():
            ind = session.query(Indicator).filter_by(
                code=code
            ).first()
            if not ind:
                ind = Indicator(
                    code=code,
                    name=info["name"],
                    category=info.get("category"),
                    unit=info.get("unit"),
                    frequency=info.get("frequency"),
                )
                session.add(ind)
                session.flush()
                count += 1

            for src_name, ext_code in info.get(
                "sources", {}
            ).items():
                src_id = source_cache.get(src_name)
                if not src_id:
                    continue
                if not session.query(
                    IndicatorSource
                ).filter_by(
                    indicator_id=ind.id,
                    source_id=src_id,
                ).first():
                    session.add(IndicatorSource(
                        indicator_id=ind.id,
                        source_id=src_id,
                        external_code=ext_code,
                        priority=1,
                    ))
        session.commit()
    finally:
        session.close()
    return count


def seed_all() -> dict[str, int]:
    """Ejecutar todos los seeds."""
    results = {}
    results["sources"] = seed_sources()
    results["currencies"] = seed_currencies()
    results["countries"] = seed_countries()
    results["exchanges"] = seed_exchanges()
    results["sectors"] = seed_sectors()
    results["indicators"] = seed_indicators()
    return results
