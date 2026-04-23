"""Cargar indicadores macro desde indicators.yml."""

from pathlib import Path

import yaml

from stonks.db import get_session
from stonks.logger import setup_logger
from stonks.models.macro import Indicator, IndicatorSource
from stonks.models.meta import DataSource

logger = setup_logger("stonks.seed")

CONFIG_DIR = Path(__file__).parent.parent / "config"


def seed_indicators() -> int:
    """Cargar indicadores y sus fuentes."""
    yml_path = CONFIG_DIR / "indicators.yml"
    with open(yml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    session = get_session()
    count = 0
    try:
        # Cache de data_sources por nombre
        source_cache: dict[str, int] = {}
        for src in session.query(DataSource).all():
            source_cache[src.name] = src.id

        for code, info in data.items():
            # Crear o buscar indicador
            ind = session.query(Indicator).filter_by(code=code).first()
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

            # Vincular fuentes
            sources = info.get("sources", {})
            for src_name, ext_code in sources.items():
                src_id = source_cache.get(src_name)
                if not src_id:
                    continue
                exists = (
                    session.query(IndicatorSource)
                    .filter_by(
                        indicator_id=ind.id,
                        source_id=src_id,
                    )
                    .first()
                )
                if not exists:
                    session.add(
                        IndicatorSource(
                            indicator_id=ind.id,
                            source_id=src_id,
                            external_code=ext_code,
                            priority=1,
                        )
                    )

        session.commit()
    finally:
        session.close()
    return count


def main() -> None:
    n = seed_indicators()
    logger.info("Indicadores cargados: %d", n)


if __name__ == "__main__":
    main()
