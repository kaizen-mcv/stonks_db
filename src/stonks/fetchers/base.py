"""Clase base para todos los fetchers."""

import json
import time
from datetime import datetime
from pathlib import Path

import requests

from stonks.config import settings
from stonks.db import get_session
from stonks.logger import get_logger
from stonks.models.meta import FetchRun

logger = get_logger("stonks.fetch")


class BaseFetcher:
    """Fetcher base con rate limiting, reintentos y
    auditoría."""

    SOURCE_NAME: str = ""
    DOMAIN: str = ""
    RATE_LIMIT: float = 1.0  # segundos entre requests
    MAX_RETRIES: int = 3

    def __init__(self) -> None:
        self._last_request: float = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "stonks/0.1.0",
                "Accept": "application/json",
            }
        )

    def _rate_limit(self) -> None:
        """Esperar si es necesario para respetar el
        rate limit."""
        elapsed = time.time() - self._last_request
        wait = self.RATE_LIMIT - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.time()

    def _get(
        self,
        url: str,
        params: dict | None = None,
    ) -> dict | list:
        """GET con rate limiting y reintentos."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            self._rate_limit()
            try:
                resp = self._session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                logger.warning(
                    "%s intento %d/%d falló: %s",
                    self.SOURCE_NAME,
                    attempt,
                    self.MAX_RETRIES,
                    e,
                )
                if attempt == self.MAX_RETRIES:
                    raise
                time.sleep(2**attempt)
        return {}

    def _start_run(self, params: dict | None = None) -> FetchRun:
        """Registrar inicio de ejecución."""
        session = get_session()
        run = FetchRun(
            domain=self.DOMAIN,
            started_at=datetime.now(),
            status="running",
            params=params,
        )
        # Buscar source_id
        from stonks.models.meta import DataSource

        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if src:
            run.source_id = src.id
        session.add(run)
        session.commit()
        run_id = run.id
        session.close()
        return run_id

    def _finish_run(
        self,
        run_id: int,
        status: str = "success",
        fetched: int = 0,
        inserted: int = 0,
        updated: int = 0,
        errors: int = 0,
        error_log: dict | None = None,
    ) -> None:
        """Registrar fin de ejecución."""
        session = get_session()
        run = session.query(FetchRun).get(run_id)
        if run:
            run.finished_at = datetime.now()
            run.status = status
            run.records_fetched = fetched
            run.records_inserted = inserted
            run.records_updated = updated
            run.errors = errors
            run.error_log = error_log
            session.commit()
        session.close()

    # ── Estado incremental ───────────────────────

    def _state_path(self, key: str) -> Path:
        """Ruta del archivo de estado."""
        state_dir = settings.state_dir
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / f"{self.SOURCE_NAME}_{key}.json"

    def _load_state(self, key: str) -> dict:
        """Cargar estado previo."""
        path = self._state_path(key)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_state(self, key: str, state: dict) -> None:
        """Guardar estado para próxima ejecución."""
        path = self._state_path(key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, default=str)
