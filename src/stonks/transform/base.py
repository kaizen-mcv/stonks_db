"""Clase base para transformaciones, con auditoría en meta."""

from abc import ABC, abstractmethod
from datetime import datetime

from stonks.db import get_session
from stonks.logger import get_logger
from stonks.models.meta import TransformRun

logger = get_logger("stonks.transform")


class BaseTransform(ABC):
    """Base de toda transformación (bronze→silver/gold).

    Aporta auditoría en meta.transform_run. Las subclases leen de las
    tablas origen, normalizan y hacen upsert idempotente
    (insert().on_conflict_do_update) en la tabla destino.
    """

    DOMAIN: str = ""
    TARGET_LAYER: str = "silver"

    def _start_run(self, params: dict | None = None) -> int:
        """Registrar inicio de transformación."""
        session = get_session()
        run = TransformRun(
            domain=self.DOMAIN,
            target_layer=self.TARGET_LAYER,
            started_at=datetime.now(),
            status="running",
            params=params,
        )
        session.add(run)
        session.commit()
        run_id = run.id
        session.close()
        return run_id

    def _finish_run(
        self,
        run_id: int,
        status: str = "success",
        records_read: int = 0,
        records_written: int = 0,
        records_invalid: int = 0,
        error_log: dict | None = None,
    ) -> None:
        """Registrar fin de transformación."""
        session = get_session()
        run = session.query(TransformRun).filter_by(id=run_id).first()
        if run:
            run.finished_at = datetime.now()
            run.status = status
            run.records_read = records_read
            run.records_written = records_written
            run.records_invalid = records_invalid
            run.error_log = error_log
            session.commit()
        session.close()

    @abstractmethod
    def transform(self, **kwargs) -> None:
        """Ejecutar la transformación."""
        ...
