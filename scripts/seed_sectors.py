"""Cargar clasificación GICS (sectores e industrias)."""

from stonks.db import get_session
from stonks.logger import setup_logger
from stonks.models.ref import Sector

logger = setup_logger("stonks.seed")

# GICS: (code, name, parent_code, level)
GICS = [
    # Nivel 1: Sectores
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
    # Nivel 2: Grupos de industria
    ("1010", "Energy", "10", 2),
    ("1510", "Materials", "15", 2),
    ("2010", "Capital Goods", "20", 2),
    ("2020", "Commercial & Professional Services", "20", 2),
    ("2030", "Transportation", "20", 2),
    ("2510", "Automobiles & Components", "25", 2),
    ("2520", "Consumer Durables & Apparel", "25", 2),
    ("2530", "Consumer Services", "25", 2),
    ("2550", "Retailing", "25", 2),
    ("3010", "Food & Staples Retailing", "30", 2),
    ("3020", "Food Beverage & Tobacco", "30", 2),
    ("3030", "Household & Personal Products", "30", 2),
    ("3510", "Health Care Equipment & Services", "35", 2),
    ("3520", "Pharmaceuticals Biotech & Life Sciences", "35", 2),
    ("4010", "Banks", "40", 2),
    ("4020", "Financial Services", "40", 2),
    ("4030", "Insurance", "40", 2),
    ("4510", "Software & Services", "45", 2),
    ("4520", "Technology Hardware & Equipment", "45", 2),
    ("4530", "Semiconductors & Equipment", "45", 2),
    ("5010", "Telecommunication Services", "50", 2),
    ("5020", "Media & Entertainment", "50", 2),
    ("5510", "Utilities", "55", 2),
    ("6010", "Equity Real Estate Investment Trusts", "60", 2),
    ("6020", "Real Estate Management & Development", "60", 2),
]


def seed_sectors() -> int:
    """Cargar sectores GICS en la BD."""
    session = get_session()
    count = 0
    # Mapa code -> id para resolver parent_id
    code_to_id: dict[str, int] = {}
    try:
        for gics_code, name, parent_code, level in GICS:
            exists = (
                session.query(Sector).filter_by(gics_code=gics_code).first()
            )
            if exists:
                code_to_id[gics_code] = exists.id
                continue
            parent_id = code_to_id.get(parent_code) if parent_code else None
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


def main() -> None:
    n = seed_sectors()
    logger.info("Sectores GICS cargados: %d", n)


if __name__ == "__main__":
    main()
