"""Cargar fuentes de datos desde sources.yml."""

from pathlib import Path

import yaml

from stonks.db import get_session
from stonks.logger import setup_logger
from stonks.models.meta import DataSource

logger = setup_logger("stonks.seed")

CONFIG_DIR = Path(__file__).parent.parent / "config"


def seed_sources() -> int:
    """Cargar fuentes de datos en meta.data_source."""
    yml_path = CONFIG_DIR / "sources.yml"
    with open(yml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    session = get_session()
    count = 0
    try:
        for name, info in data.items():
            exists = session.query(DataSource).filter_by(
                name=name
            ).first()
            if exists:
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


def main() -> None:
    n = seed_sources()
    logger.info("Fuentes cargadas: %d", n)


if __name__ == "__main__":
    main()
