"""Reconstrucción del universo S&P 500 point-in-time (survivorship-free).

Lee los intervalos crudos de bronze (github_intervals) y construye
gold.index_membership. Crea empresas-shell para los tickers históricos
que no teníamos (los marca deslistados) y puebla la foto actual en
equity.index_constituent_current. Tras esto, el benchmark equiponderado
de gold deja de tener sesgo de supervivencia.
"""

from datetime import date

from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.gold.build import SP500_CODES
from stonks.models.bronze import ConstituentsSnapshot
from stonks.models.equity import (
    Company,
    IndexConstituentCurrent,
    MarketIndex,
)
from stonks.models.gold import IndexMembership
from stonks.transform.base import BaseTransform, logger


def _to_date(value: str | None) -> date | None:
    """Convertir 'YYYY-MM-DD' a date (None si vacío)."""
    if not value:
        return None
    return date.fromisoformat(value)


def _yahoo_ticker(ticker: str) -> str:
    """Normalizar ticker fja05680 al estilo Yahoo (BRK.B → BRK-B)."""
    return ticker.replace(".", "-")


class MembershipTransform(BaseTransform):
    """Construye el universo histórico del S&P 500 y marca deslistadas."""

    DOMAIN = "index_membership"
    TARGET_LAYER = "gold"

    def transform(self) -> None:
        """Reconstruir membership desde el último payload de intervalos."""
        run_id = self._start_run()
        session = get_session()
        read = written = created = 0
        try:
            index_id = self._sp500_index_id(session)
            if index_id is None:
                raise RuntimeError("No existe el índice S&P 500 (SPX)")

            intervals = self._latest_intervals(session)
            by_ticker = self._group_by_ticker(intervals)
            read = len(intervals)

            for ticker, ivals in by_ticker.items():
                is_current = any(end is None for _, end in ivals)
                max_end = max(
                    (end for _, end in ivals if end is not None),
                    default=None,
                )
                company_id, nuevo = self._ensure_company(
                    session, ticker, is_current, max_end
                )
                created += int(nuevo)
                for start, end in ivals:
                    self._upsert_membership(
                        session, index_id, company_id, ticker, start, end
                    )
                    written += 1
                if is_current:
                    self._upsert_current(session, index_id, company_id)
            session.commit()

            self._finish_run(
                run_id,
                "success",
                records_read=read,
                records_written=written,
            )
            logger.info(
                "Membership: %d intervalos, %d empresas creadas (deslistadas)",
                written,
                created,
            )
        except Exception as e:  # noqa: BLE001
            session.rollback()
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("MembershipTransform falló: %s", e)
        finally:
            session.close()

    @staticmethod
    def _sp500_index_id(session) -> int | None:
        """Id del índice S&P 500 en equity.market_index."""
        row = (
            session.query(MarketIndex.id)
            .filter(MarketIndex.code.in_(SP500_CODES))
            .first()
        )
        return row[0] if row else None

    @staticmethod
    def _latest_intervals(session) -> list[list]:
        """Último payload github_intervals de bronze → lista de filas."""
        snap = (
            session.query(ConstituentsSnapshot)
            .filter_by(index_code="SP500", source_kind="github_intervals")
            .order_by(ConstituentsSnapshot.ingested_at.desc())
            .first()
        )
        if snap is None:
            return []
        return snap.payload.get("rows", [])

    @staticmethod
    def _group_by_ticker(rows: list[list]) -> dict[str, list]:
        """Agrupar intervalos por ticker: {ticker: [(start, end), ...]}."""
        grouped: dict[str, list] = {}
        for ticker, start, end in rows:
            grouped.setdefault(ticker, []).append(
                (_to_date(start), _to_date(end))
            )
        return grouped

    @staticmethod
    def _ensure_company(
        session, ticker: str, is_current: bool, max_end: date | None
    ) -> tuple[int, bool]:
        """Devolver (company_id, creada). Crea shell si no existe.

        Las empresas creadas que ya no son miembros se marcan deslistadas
        (señal survivorship-free). Las ya existentes no se tocan: pueden
        seguir cotizando aunque salieran del índice.
        """
        yticker = _yahoo_ticker(ticker)
        company = (
            session.query(Company).filter(Company.ticker == yticker).first()
        )
        if company is not None:
            return company.id, False

        company = Company(
            ticker=yticker,
            name=ticker,
            is_active=is_current,
            delisted_date=None if is_current else max_end,
        )
        session.add(company)
        session.flush()
        return company.id, True

    @staticmethod
    def _upsert_membership(
        session, index_id, company_id, ticker, start, end
    ) -> None:
        """Upsert idempotente en gold.index_membership."""
        stmt = insert(IndexMembership).values(
            index_id=index_id,
            company_id=company_id,
            ticker=ticker,
            start_date=start,
            end_date=end,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["index_id", "company_id", "start_date"],
            set_={
                "end_date": stmt.excluded.end_date,
                "ticker": stmt.excluded.ticker,
            },
        )
        session.execute(stmt)

    @staticmethod
    def _upsert_current(session, index_id, company_id) -> None:
        """Upsert del constituyente actual en equity."""
        stmt = insert(IndexConstituentCurrent).values(
            index_id=index_id,
            company_id=company_id,
            as_of_date=date.today(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["index_id", "company_id"],
            set_={"as_of_date": stmt.excluded.as_of_date},
        )
        session.execute(stmt)
