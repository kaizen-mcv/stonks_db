"""Cargar bolsas de valores principales."""

from stonks.db import get_session
from stonks.logger import setup_logger
from stonks.models.ref import Exchange

logger = setup_logger("stonks.seed")

# Bolsas principales con MIC, país y zona horaria
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
    ("XAMS", "Euronext Amsterdam",
     "Euronext Amsterdam",
     "NLD", "Amsterdam", "Europe/Amsterdam", "EUR"),
    ("XBRU", "Euronext Brussels",
     "Euronext Brussels",
     "BEL", "Brussels", "Europe/Brussels", "EUR"),
    ("XLIS", "Euronext Lisbon", "Euronext Lisbon",
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
    ("XSTO", "OMX Stockholm", "Nasdaq Stockholm",
     "SWE", "Stockholm", "Europe/Stockholm", "SEK"),
    ("XHEL", "OMX Helsinki", "Nasdaq Helsinki",
     "FIN", "Helsinki", "Europe/Helsinki", "EUR"),
    ("XOSL", "Oslo Børs", "Oslo Stock Exchange",
     "NOR", "Oslo", "Europe/Oslo", "NOK"),
    ("XCSE", "OMX Copenhagen",
     "Nasdaq Copenhagen",
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
    ("XKLS", "Bursa Malaysia", "Bursa Malaysia",
     "MYS", "Kuala Lumpur", "Asia/Kuala_Lumpur",
     "MYR"),
]


def seed_exchanges() -> int:
    """Cargar bolsas en la BD."""
    session = get_session()
    count = 0
    try:
        for (mic, short, name, country,
             city, tz, currency) in EXCHANGES:
            exists = session.query(Exchange).filter_by(
                mic=mic
            ).first()
            if exists:
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


def main() -> None:
    n = seed_exchanges()
    logger.info("Bolsas cargadas: %d", n)


if __name__ == "__main__":
    main()
