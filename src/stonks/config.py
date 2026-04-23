"""Configuración centralizada con Pydantic."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="STONKS_",
    )

    # Configurar via STONKS_DB_URL en .env
    db_url: str = "postgresql+psycopg://localhost/stonks_db"

    # API keys (opcionales)
    fred_api_key: str = ""
    alpha_vantage_key: str = ""
    coingecko_key: str = ""

    # Rate limiting por defecto
    default_rate_limit: float = 1.0
    default_max_retries: int = 3

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def downloads_dir(self) -> Path:
        return self.data_dir / "downloads"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def config_dir(self) -> Path:
        return PROJECT_ROOT / "config"


settings = Settings()
