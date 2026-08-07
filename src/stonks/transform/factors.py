"""Cálculo de factores cross-section → gold.fact_factor_scores.

Factores Value/Quality/Momentum normalizados por z-score global y por
z-score dentro del sector GICS (sector-neutral), lo que evita el sesgo
sectorial en el ranking de kairos_bot.

Es **point-in-time replayable**: para una fecha as_of usa solo
fundamentales con filed_date <= as_of y precios <= as_of, sin datos del
futuro. Esto permite reconstruir el panel de factores en cualquier fecha
pasada (transform_history) para backtests honestos.

- value (earnings yield) = eps_diluted(PIT) / precio(as_of)
- quality (ROE)          = net_income(PIT) / total_equity(PIT)
- momentum (12-1)        = precio(as_of-21d) / precio(as_of-365d) - 1

El universo es el S&P 500 **point-in-time** (gold.index_membership): solo
las empresas que pertenecían al índice en la fecha as_of.
"""

from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import engine, get_session
from stonks.gold.build import SP500_CODES
from stonks.models.gold import FactFactorScores
from stonks.transform.base import BaseTransform, logger

UNIVERSE = "sp500_pit"


class FactorScoreTransform(BaseTransform):
    """Construye scores de factores PIT normalizados por sector."""

    DOMAIN = "factors"
    TARGET_LAYER = "gold"

    def transform(self, as_of: date | None = None) -> None:
        """Calcular factores para el universo S&P 500 PIT en as_of."""
        as_of = as_of or date.today()
        run_id = self._start_run(params={"as_of": as_of.isoformat()})
        try:
            written = self._run_one(as_of)
            self._finish_run(run_id, "success", records_written=written)
            logger.info("Factores %s: %d scores", as_of, written)
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("FactorScoreTransform falló: %s", e)

    def transform_history(
        self, start: date, end: date | None = None, freq: str = "ME"
    ) -> None:
        """Calcular el panel de factores en fechas de rebalanceo.

        Itera fin de mes (freq='ME') entre start y end y calcula los
        factores PIT en cada fecha → historial para backtests. Es
        idempotente: re-ejecutar recomputa cada fecha.
        """
        end = end or date.today()
        fechas = pd.date_range(start, end, freq=freq)
        run_id = self._start_run(
            params={"start": start.isoformat(), "end": end.isoformat()}
        )
        total = 0
        try:
            for ts in fechas:
                total += self._run_one(ts.date())
            self._finish_run(run_id, "success", records_written=total)
            logger.info(
                "Factores historia %s→%s: %d fechas, %d scores",
                start,
                end,
                len(fechas),
                total,
            )
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("transform_history falló: %s", e)

    def _run_one(self, as_of: date) -> int:
        """Calcular y volcar los factores de una sola fecha."""
        df = self._build_panel(as_of)
        if df.empty:
            return 0
        scores = self._score(df)
        return self._upsert(scores, as_of)

    @staticmethod
    def _universe(as_of: date) -> pd.DataFrame:
        """Miembros del S&P 500 en as_of (con sector)."""
        codes = ",".join(f"'{c}'" for c in SP500_CODES)
        sql = text(
            "SELECT DISTINCT m.company_id, c.sector_id "
            "FROM gold.index_membership m "
            "JOIN equity.company c ON c.id = m.company_id "
            "JOIN equity.market_index mi ON mi.id = m.index_id "
            f"WHERE mi.code IN ({codes}) "
            "  AND m.start_date <= :asof "
            "  AND (m.end_date IS NULL OR :asof < m.end_date) "
            "  AND c.sector_id IS NOT NULL"
        )
        with engine.connect() as c:
            return pd.read_sql(sql, c, params={"asof": as_of}).set_index(
                "company_id"
            )

    @staticmethod
    def _latest_metric(as_of: date, metric: str) -> pd.Series:
        """Último valor anual PIT por empresa con filed <= as_of."""
        sql = text(
            "SELECT DISTINCT ON (company_id) company_id, value "
            "FROM gold.fact_fundamentals_pit "
            "WHERE metric = :m AND fiscal_quarter IS NULL "
            "  AND filed_date <= :asof "
            "ORDER BY company_id, filed_date DESC, fiscal_year DESC"
        )
        with engine.connect() as c:
            return pd.read_sql(
                sql, c, params={"m": metric, "asof": as_of}
            ).set_index("company_id")["value"]

    @staticmethod
    def _prices_at(as_of: date, ids: list[int]) -> pd.Series:
        """Último cierre <= as_of por empresa."""
        if not ids:
            return pd.Series(dtype=float)
        sql = text(
            "SELECT DISTINCT ON (company_id) company_id, close "
            "FROM equity.price_daily "
            "WHERE company_id = ANY(:ids) AND date <= :asof "
            "ORDER BY company_id, date DESC"
        )
        with engine.connect() as c:
            return pd.read_sql(
                sql, c, params={"ids": ids, "asof": as_of}
            ).set_index("company_id")["close"]

    def _build_panel(self, as_of: date) -> pd.DataFrame:
        """Panel de factores crudos PIT por empresa."""
        df = self._universe(as_of)
        if df.empty:
            return df
        ids = df.index.tolist()
        eps = self._latest_metric(as_of, "eps_diluted")
        net_income = self._latest_metric(as_of, "net_income")
        equity = self._latest_metric(as_of, "total_equity")
        price = self._prices_at(as_of, ids)
        momentum = self._momentum(as_of, ids)

        df["eps"] = eps
        df["price"] = price
        df["net_income"] = net_income
        df["total_equity"] = equity
        df["momentum"] = momentum
        # Factores crudos (PIT-safe)
        df["value"] = df["eps"].astype(float) / df["price"].astype(float)
        df["quality"] = df["net_income"].astype(float) / df[
            "total_equity"
        ].astype(float)
        df = df.dropna(subset=["value", "quality", "momentum"], how="all")
        return df

    @staticmethod
    def _momentum(as_of: date, company_ids: list[int]) -> pd.Series:
        """Momentum 12-1: close(t-21d) / close(t-365d) - 1."""
        if not company_ids:
            return pd.Series(dtype=float)
        with engine.connect() as c:
            prices = pd.read_sql(
                text(
                    "SELECT company_id, date, close FROM equity.price_daily "
                    "WHERE company_id = ANY(:ids) "
                    "  AND date >= :floor AND date <= :asof"
                ),
                c,
                params={
                    "ids": company_ids,
                    "floor": as_of - pd.Timedelta(days=420),
                    "asof": as_of,
                },
            )
        if prices.empty:
            return pd.Series(dtype=float)
        prices["date"] = pd.to_datetime(prices["date"])
        out = {}
        skip = as_of - pd.Timedelta(days=21)
        base = as_of - pd.Timedelta(days=365)
        for cid, grp in prices.groupby("company_id"):
            grp = grp.sort_values("date")
            p_skip = _closest(grp, skip)
            p_base = _closest(grp, base)
            if p_skip and p_base and p_base != 0:
                out[cid] = p_skip / p_base - 1
        return pd.Series(out, dtype=float)

    @staticmethod
    def _score(df: pd.DataFrame) -> pd.DataFrame:
        """z-score global y sector-neutral + percentil por factor."""
        registros = []
        for factor in ("value", "quality", "momentum"):
            serie = df[factor].astype(float)
            z = _zscore(serie)
            z_sec = serie.groupby(df["sector_id"]).transform(_zscore)
            # `rank(pct=True)` da 0-1; la columna se llama `percentile`
            # y debe ir en 0-100, como el resto de columnas de
            # porcentaje del proyecto.
            pct = serie.rank(pct=True) * 100
            for cid in df.index:
                if pd.isna(serie[cid]):
                    continue
                registros.append(
                    {
                        "company_id": int(cid),
                        "factor": factor,
                        "raw_value": float(serie[cid]),
                        "z_score": _f(z[cid]),
                        "z_sector_neutral": _f(z_sec[cid]),
                        "percentile": _f(pct[cid]),
                    }
                )
        return pd.DataFrame(registros)

    @staticmethod
    def _upsert(scores: pd.DataFrame, as_of: date) -> int:
        """Upsert idempotente de scores."""
        if scores.empty:
            return 0
        session = get_session()
        n = 0
        try:
            for row in scores.to_dict(orient="records"):
                row["as_of_date"] = as_of
                row["universe"] = UNIVERSE
                stmt = insert(FactFactorScores).values(**row)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[
                        "company_id",
                        "as_of_date",
                        "factor",
                        "universe",
                    ],
                    set_={
                        "raw_value": stmt.excluded.raw_value,
                        "z_score": stmt.excluded.z_score,
                        "z_sector_neutral": stmt.excluded.z_sector_neutral,
                        "percentile": stmt.excluded.percentile,
                    },
                )
                session.execute(stmt)
                n += 1
            session.commit()
        finally:
            session.close()
        return n


def _closest(grp: pd.DataFrame, target) -> float | None:
    """Close de la fecha más cercana al objetivo (o None)."""
    idx = (grp["date"] - pd.Timestamp(target)).abs().idxmin()
    return float(grp.loc[idx, "close"])


def _zscore(serie: pd.Series) -> pd.Series:
    """z-score robusto (std poblacional); 0 si no hay dispersión."""
    s = serie.astype(float)
    std = s.std(ddof=0)
    if not std or pd.isna(std):
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / std


def _f(value) -> float | None:
    """Convertir a float nativo o None (para JSON/SQL)."""
    if value is None or pd.isna(value):
        return None
    return float(value)
