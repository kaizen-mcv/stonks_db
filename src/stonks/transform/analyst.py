"""bronze.analyst_snapshot → equity.analyst_estimate + earnings_revision.

Normaliza la foto diaria de analistas (yfinance) a dos tablas silver,
indexadas por (company_id, snapshot_date, horizon). Idempotente por día.
"""

from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.models.bronze import AnalystSnapshot
from stonks.models.equity import (
    AnalystEstimate,
    Company,
    EarningsRevision,
)
from stonks.transform.base import BaseTransform, logger


class AnalystTransform(BaseTransform):
    """Construye estimaciones y revisiones desde bronze."""

    DOMAIN = "analyst"
    TARGET_LAYER = "silver"

    def transform(self) -> None:
        """Procesar las fotos de bronze no volcadas aún."""
        run_id = self._start_run()
        session = get_session()
        read = written = 0
        try:
            for snap in session.query(AnalystSnapshot).all():
                company_id = self._company_id(session, snap.ticker)
                if company_id is None:
                    continue
                read += 1
                written += self._volcar(
                    session, company_id, snap.snapshot_date, snap.payload
                )
            session.commit()
            self._finish_run(
                run_id,
                "success",
                records_read=read,
                records_written=written,
            )
            logger.info("Analistas: %d fotos, %d filas", read, written)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("AnalystTransform falló: %s", e)
        finally:
            session.close()

    @staticmethod
    def _company_id(session, ticker: str) -> int | None:
        row = (
            session.query(Company.id).filter(Company.ticker == ticker).first()
        )
        return row[0] if row else None

    def _volcar(self, session, company_id, snap_date, payload) -> int:
        """Insertar estimaciones y revisiones de una foto."""
        ee = payload.get("earnings_estimate", {})
        re = payload.get("revenue_estimate", {})
        et = payload.get("eps_trend", {})
        er = payload.get("eps_revisions", {})
        horizontes = set(ee) | set(et)
        n = 0
        for h in horizontes:
            est = ee.get(h, {})
            rev_est = re.get(h, {})
            self._upsert_estimate(
                session, company_id, snap_date, h, est, rev_est
            )
            trend = et.get(h, {})
            revs = er.get(h, {})
            self._upsert_revision(
                session, company_id, snap_date, h, trend, revs
            )
            n += 1
        return n

    @staticmethod
    def _upsert_estimate(session, cid, snap_date, h, est, rev_est) -> None:
        stmt = insert(AnalystEstimate).values(
            company_id=cid,
            snapshot_date=snap_date,
            horizon=h,
            eps_avg=est.get("avg"),
            eps_low=est.get("low"),
            eps_high=est.get("high"),
            revenue_avg=rev_est.get("avg"),
            num_analysts=est.get("numberOfAnalysts"),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["company_id", "snapshot_date", "horizon"],
            set_={
                "eps_avg": stmt.excluded.eps_avg,
                "eps_low": stmt.excluded.eps_low,
                "eps_high": stmt.excluded.eps_high,
                "revenue_avg": stmt.excluded.revenue_avg,
                "num_analysts": stmt.excluded.num_analysts,
            },
        )
        session.execute(stmt)

    @staticmethod
    def _upsert_revision(session, cid, snap_date, h, trend, revs) -> None:
        stmt = insert(EarningsRevision).values(
            company_id=cid,
            snapshot_date=snap_date,
            horizon=h,
            eps_current=trend.get("current"),
            eps_7d_ago=trend.get("7daysAgo"),
            eps_30d_ago=trend.get("30daysAgo"),
            up_last_30d=revs.get("upLast30days"),
            down_last_30d=revs.get("downLast30days"),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["company_id", "snapshot_date", "horizon"],
            set_={
                "eps_current": stmt.excluded.eps_current,
                "eps_7d_ago": stmt.excluded.eps_7d_ago,
                "eps_30d_ago": stmt.excluded.eps_30d_ago,
                "up_last_30d": stmt.excluded.up_last_30d,
                "down_last_30d": stmt.excluded.down_last_30d,
            },
        )
        session.execute(stmt)
