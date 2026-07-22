"""Parseo de SEC companyfacts → gold.fact_fundamentals_pit.

Recorre los conceptos XBRL us-gaap seleccionados y emite una fila por
métrica/periodo/fecha-de-publicación (formato long). El grano incluye
filed_date, así que un restatement de la misma fiscal-period queda como
otra fila (no pisa la anterior): así se puede consultar el valor
'tal como se conocía' en cualquier fecha pasada.
"""

from datetime import date

from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.models.bronze import SecCompanyFacts
from stonks.models.equity import Company
from stonks.models.gold import FactFundamentalsPit
from stonks.transform.base import BaseTransform, logger

# metric → (statement_type, unit, [conceptos XBRL alternativos])
METRIC_CONCEPTS: dict[str, tuple[str, str, list[str]]] = {
    "revenue": (
        "income",
        "USD",
        [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ],
    ),
    "gross_profit": ("income", "USD", ["GrossProfit"]),
    "operating_income": ("income", "USD", ["OperatingIncomeLoss"]),
    "net_income": ("income", "USD", ["NetIncomeLoss"]),
    "eps_diluted": ("income", "USD/shares", ["EarningsPerShareDiluted"]),
    "total_assets": ("balance", "USD", ["Assets"]),
    "total_liabilities": ("balance", "USD", ["Liabilities"]),
    "total_equity": ("balance", "USD", ["StockholdersEquity"]),
    "cash": (
        "balance",
        "USD",
        ["CashAndCashEquivalentsAtCarryingValue"],
    ),
    "operating_cash_flow": (
        "cashflow",
        "USD",
        ["NetCashProvidedByUsedInOperatingActivities"],
    ),
}


def _quarter(fp: str | None) -> int | None:
    """Trimestre fiscal desde 'fp' (FY→None, Q1..Q4→1..4)."""
    if not fp or fp == "FY":
        return None
    if fp.startswith("Q") and fp[1:].isdigit():
        return int(fp[1:])
    return None


def _classify_period(
    start: str | None, end: str | None, fp: str | None
) -> tuple[bool, int | None] | None:
    """Clasificar un hecho por la duración real del periodo.

    SEC mezcla importes anuales, trimestrales y acumulados (6m/9m) para
    el mismo concepto. Devuelve (es_valido, fiscal_quarter) o None si no
    es ni un año ni un trimestre limpio:
    - ~365 días → anual (fiscal_quarter=None)
    - ~90 días  → trimestral (fiscal_quarter de 'fp'; None si no se sabe)
    """
    if not start:
        # Concepto instantáneo (balance): el periodo lo marca 'fp'.
        return True, _quarter(fp)
    dias = (date.fromisoformat(end) - date.fromisoformat(start)).days
    if 350 <= dias <= 380:
        return True, None
    if 80 <= dias <= 100:
        fq = _quarter(fp)
        return (True, fq) if fq is not None else None
    # Acumulados intermedios (6m/9m) u otros: se descartan.
    return None


class FundamentalsPitTransform(BaseTransform):
    """Construye gold.fact_fundamentals_pit desde bronze."""

    DOMAIN = "fundamentals_pit"
    TARGET_LAYER = "gold"

    def transform(
        self,
        tickers: list[str] | None = None,
        skip_done: bool = True,
    ) -> None:
        """Procesar el último companyfacts por CIK (o por ticker dado).

        Procesa un payload a la vez y commitea por empresa: los payloads
        de SEC pesan varios MB, así que cargarlos todos a la vez agota la
        memoria. Reusa el JSON ya en bronze (no vuelve a descargar).
        Con skip_done=True salta las empresas que ya tienen PIT (permite
        reanudar por tramos si el proceso se interrumpe).
        """
        run_id = self._start_run(params={"tickers": tickers})
        read = written = 0
        try:
            ids = self._latest_snapshot_ids(tickers, skip_done)
            for snap_id in ids:
                written += self._process_one(snap_id)
                read += 1
                if read % 100 == 0:
                    logger.info("PIT %d/%d", read, len(ids))
            self._finish_run(
                run_id,
                "success",
                records_read=read,
                records_written=written,
            )
            logger.info("PIT: %d empresas, %d hechos escritos", read, written)
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("FundamentalsPitTransform falló: %s", e)

    def _process_one(self, snap_id: int) -> int:
        """Cargar un snapshot, volcarlo a gold y commitear."""
        session = get_session()
        try:
            snap = session.query(SecCompanyFacts).filter_by(id=snap_id).first()
            company_id = self._company_id(session, snap.ticker)
            if company_id is None:
                return 0
            rows = self._extract_rows(snap.payload, company_id)
            n = self._upsert(session, rows)
            session.commit()
            return n
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.warning("PIT snapshot %s falló: %s", snap_id, e)
            return 0
        finally:
            session.close()

    @staticmethod
    def _latest_snapshot_ids(tickers, skip_done: bool = False) -> list[int]:
        """IDs del último snapshot por CIK (sin cargar payloads).

        Con skip_done omite los tickers cuya empresa ya tiene PIT.
        """
        from sqlalchemy import text

        session = get_session()
        try:
            done: set[str] = set()
            if skip_done:
                done = {
                    r[0]
                    for r in session.execute(
                        text(
                            "SELECT DISTINCT c.ticker FROM equity.company c "
                            "JOIN gold.fact_fundamentals_pit f "
                            "  ON f.company_id = c.id"
                        )
                    )
                }
            query = session.query(
                SecCompanyFacts.id,
                SecCompanyFacts.cik,
                SecCompanyFacts.ticker,
            ).order_by(SecCompanyFacts.cik, SecCompanyFacts.ingested_at.desc())
            if tickers:
                ups = [t.upper() for t in tickers]
                query = query.filter(SecCompanyFacts.ticker.in_(ups))
            vistos: set[str] = set()
            ids: list[int] = []
            for snap_id, cik, ticker in query:
                if cik in vistos:
                    continue
                vistos.add(cik)
                if ticker in done:
                    continue
                ids.append(snap_id)
            return ids
        finally:
            session.close()

    @staticmethod
    def _company_id(session, ticker: str) -> int | None:
        """Id de empresa por ticker."""
        row = (
            session.query(Company.id).filter(Company.ticker == ticker).first()
        )
        return row[0] if row else None

    # Unidades numéricas que capturamos del XBRL (en orden de preferencia)
    _UNITS = ("USD", "USD/shares", "shares", "pure")

    @staticmethod
    def _extract_rows(payload: dict, company_id: int) -> list[dict]:
        """Aplanar companyfacts a filas long (dedup en lote).

        Dos pasadas: (1) métricas amigables curadas (net_income, ...) que
        consumen factores y panel; (2) **todos** los conceptos XBRL de
        us-gaap y dei con metric=concepto (máxima profundidad).
        """
        facts = payload.get("facts", {})
        usgaap = facts.get("us-gaap", {})
        dedup: dict[tuple, dict] = {}
        # (1) Métricas amigables (compatibilidad con factors/panel)
        for metric, (stmt, unit, conceptos) in METRIC_CONCEPTS.items():
            concept = next((c for c in conceptos if c in usgaap), None)
            if concept is None:
                continue
            items = usgaap[concept].get("units", {}).get(unit, [])
            FundamentalsPitTransform._collect(
                items, stmt, metric, company_id, "USD", dedup
            )
        # (2) Todos los conceptos XBRL (profundidad completa)
        for taxonomy in ("us-gaap", "dei"):
            for concept, cdata in facts.get(taxonomy, {}).items():
                units = cdata.get("units", {})
                unit = next(
                    (u for u in FundamentalsPitTransform._UNITS if u in units),
                    None,
                )
                if unit is None:
                    continue
                cur = "USD" if unit == "USD" else None
                FundamentalsPitTransform._collect(
                    units[unit],
                    taxonomy,
                    concept[:150],
                    company_id,
                    cur,
                    dedup,
                )
        return list(dedup.values())

    @staticmethod
    def _collect(items, stmt, metric, company_id, currency, dedup) -> None:
        """Añadir a `dedup` las filas válidas de un concepto."""
        for it in items:
            filed = it.get("filed")
            end = it.get("end")
            fy = it.get("fy")
            val = it.get("val")
            if not (filed and end and fy) or val is None:
                continue
            # Descartar valores no numéricos o absurdos (overflow).
            if not isinstance(val, (int, float)) or abs(val) >= 1e26:
                continue
            clasif = _classify_period(it.get("start"), end, it.get("fp"))
            if clasif is None:
                continue
            _, fq = clasif
            key = (company_id, stmt, fy, fq, filed, metric)
            dedup[key] = {
                "company_id": company_id,
                "statement_type": stmt,
                "fiscal_year": fy,
                "fiscal_quarter": fq,
                "period_end_date": date.fromisoformat(end),
                "filed_date": date.fromisoformat(filed),
                "publish_date": date.fromisoformat(filed),
                "metric": metric,
                "value": val,
                "currency_code": currency,
                "form": it.get("form"),
            }

    @staticmethod
    def _upsert(session, rows: list[dict]) -> int:
        """Upsert idempotente en gold.fact_fundamentals_pit.

        Troceado: con todos los conceptos XBRL hay miles de filas por
        empresa y Postgres limita a 65535 parámetros por sentencia.
        """
        if not rows:
            return 0
        chunk = 4000
        for i in range(0, len(rows), chunk):
            stmt = insert(FactFundamentalsPit).values(rows[i : i + chunk])
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    "company_id",
                    "statement_type",
                    "fiscal_year",
                    "fiscal_quarter",
                    "filed_date",
                    "metric",
                ],
                set_={
                    "value": stmt.excluded.value,
                    "form": stmt.excluded.form,
                },
            )
            session.execute(stmt)
        return len(rows)
