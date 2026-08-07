"""Datos 360° de cada empresa (yfinance): profundidad máxima.

Captura lo que la ingesta básica ignora: accionistas institucionales y
fondos, operaciones de insiders, cambios de recomendación/precio objetivo,
resumen de recomendaciones, histórico de acciones en circulación,
calendario de resultados y el perfil `.info` completo (a bronze).

yfinance es frágil y cambia de forma: cada atributo se envuelve en
try/except; lo que falle se omite sin abortar el resto.
"""

from datetime import date

import pandas as pd
import yfinance as yf
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.bronze import YfProfile
from stonks.models.equity import (
    EarningsDate,
    Holder,
    InsiderTransaction,
    RecommendationTrend,
    SharesHistory,
    UpgradeDowngrade,
)
from stonks.utils.divisas import tipo_de_cambio


def _num(v):
    """float nativo o None (descarta NaN)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v):
    n = _num(v)
    return int(n) if n is not None else None


def _pct(v):
    """Fracción de Yahoo a porcentaje (0,0847 -> 8,47)."""
    n = _num(v)
    return None if n is None else n * 100


def _a_usd(v, factor):
    """Importe en moneda de cotización a dólares."""
    n = _num(v)
    if n is None or factor is None:
        return None
    return n * factor


def _d(v):
    """Convertir a date o None."""
    try:
        ts = pd.Timestamp(v)
        return None if pd.isna(ts) else ts.date()
    except (TypeError, ValueError):
        return None


class EquityDeepFetcher(BaseFetcher):
    """Descarga la ficha 360° de las empresas."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "equity"
    RATE_LIMIT = 0.5

    def fetch_batch(self, tickers: list[str] | None = None) -> dict:
        """Capturar el 360° para varios tickers (o todos los activos)."""
        pares = self._targets(tickers)
        stats = {"empresas": 0, "con_datos": 0}
        total = len(pares)
        # Registrar la ejecución: además de dejar rastro en
        # `meta.fetch_run`, es lo que da el `fetch_run_id` que se
        # estampa en cada fila.
        run_id = self._start_run(params={"tickers": len(pares)})
        for i, (ticker, cid) in enumerate(pares, 1):
            self._rate_limit()
            stats["empresas"] += 1
            if self._fetch_one(ticker, cid):
                stats["con_datos"] += 1
            if i % 50 == 0:
                logger.info("Deep %d/%d", i, total)
        logger.info("Equity 360°: %d/%d con datos", stats["con_datos"], total)
        self._finish_run(
            run_id,
            "success",
            fetched=stats["empresas"],
            inserted=stats["con_datos"],
        )
        return stats

    def fetch(self, tickers: list[str] | None = None) -> dict:
        return self.fetch_batch(tickers)

    def _fetch_one(self, ticker: str, cid: int) -> bool:
        """Capturar y volcar el 360° de una empresa."""
        t = yf.Ticker(ticker)
        hoy = date.today()
        # Los importes vienen en la moneda de cotización y las
        # columnas se llaman `_usd`. El factor se calcula una vez por
        # empresa, no una por fila.
        factor = self._factor_usd(cid)
        algo = False
        algo |= self._profile(t, ticker, hoy)
        algo |= self._holders(t, cid, hoy, factor)
        algo |= self._insiders(t, cid, factor)
        algo |= self._upgrades(t, cid)
        algo |= self._recommendations(t, cid, hoy)
        algo |= self._shares(t, cid)
        algo |= self._earnings_dates(t, cid)
        return algo

    @staticmethod
    def _factor_usd(cid: int) -> float | None:
        """Factor que pasa a dólares los importes de una empresa.

        Yahoo informa el valor de una participación o de una operación
        de insider en la moneda en que cotiza el valor: la posición de
        Vanguard en Samsung figuraba con 18 billones, que son wones.

        Devuelve None si la empresa cotiza en una moneda sin tipo de
        cambio reciente; en ese caso el importe se descarta, porque un
        número sin unidad conocida es peor que ninguno.
        """
        with get_session() as session:
            moneda = session.execute(
                text(
                    "SELECT currency_code FROM equity.company "
                    "WHERE id = :cid"
                ),
                {"cid": cid},
            ).scalar()

            # Sin moneda declarada no se toca el importe: son sobre
            # todo cotizadas estadounidenses, que ya están en dólares.
            if not moneda or moneda == "USD":
                return 1.0

            tipo = tipo_de_cambio(session, moneda)
            return None if tipo is None else 1.0 / tipo

    # ── secciones ────────────────────────────────────

    def _profile(self, t, ticker, hoy) -> bool:
        try:
            info = t.info
            if not info:
                return False
        except Exception:  # noqa: BLE001
            return False
        import json

        payload = json.loads(json.dumps(info, default=str))
        self._upsert(
            YfProfile,
            [{"ticker": ticker, "snapshot_date": hoy, "payload": payload}],
            ["ticker", "snapshot_date"],
            {"payload"},
        )
        return True

    def _holders(self, t, cid, hoy, factor) -> bool:
        filas = []
        for attr, tipo in (
            ("institutional_holders", "institutional"),
            ("mutualfund_holders", "mutualfund"),
        ):
            try:
                df = getattr(t, attr)
            except Exception:  # noqa: BLE001
                continue
            if df is None or df.empty:
                continue
            for _, r in df.iterrows():
                nombre = str(r.get("Holder") or "")[:200]
                if not nombre:
                    continue
                filas.append(
                    {
                        "company_id": cid,
                        "holder_type": tipo,
                        "holder_name": nombre,
                        "snapshot_date": hoy,
                        "date_reported": _d(r.get("Date Reported")),
                        # Yahoo da `pctHeld` como fracción (0,0847),
                        # no como porcentaje. Se guarda en porcentaje
                        # para que la columna diga lo que su nombre
                        # promete.
                        "pct_held": _pct(r.get("pctHeld")),
                        "shares": _int(r.get("Shares")),
                        "value_usd": _a_usd(r.get("Value"), factor),
                    }
                )
        return self._upsert(
            Holder,
            filas,
            ["company_id", "holder_type", "holder_name", "snapshot_date"],
            {"pct_held", "shares", "value_usd", "date_reported"},
        )

    def _insiders(self, t, cid, factor) -> bool:
        try:
            df = t.insider_transactions
        except Exception:  # noqa: BLE001
            return False
        if df is None or df.empty:
            return False
        filas = []
        for _, r in df.iterrows():
            filas.append(
                {
                    "company_id": cid,
                    "insider": str(r.get("Insider") or "")[:200],
                    "position": str(r.get("Position") or "")[:200] or None,
                    "transaction": str(r.get("Transaction") or "")[:100]
                    or None,
                    "start_date": _d(r.get("Start Date")),
                    "shares": _int(r.get("Shares")),
                    "value_usd": _a_usd(r.get("Value"), factor),
                }
            )
        return self._upsert(
            InsiderTransaction,
            filas,
            ["company_id", "insider", "start_date", "shares", "transaction"],
            {"position", "value_usd"},
        )

    def _upgrades(self, t, cid) -> bool:
        try:
            df = t.upgrades_downgrades
        except Exception:  # noqa: BLE001
            return False
        if df is None or df.empty:
            return False
        filas = []
        for idx, r in df.iterrows():
            fecha = _d(idx)
            firma = str(r.get("Firm") or "")[:200]
            if not fecha or not firma:
                continue
            filas.append(
                {
                    "company_id": cid,
                    "date": fecha,
                    "firm": firma,
                    "to_grade": str(r.get("ToGrade") or "")[:100] or None,
                    "from_grade": str(r.get("FromGrade") or "")[:100] or None,
                    "action": str(r.get("Action") or "")[:50] or None,
                    "price_target": _num(r.get("currentPriceTarget")),
                }
            )
        return self._upsert(
            UpgradeDowngrade,
            filas,
            ["company_id", "date", "firm", "to_grade"],
            {"from_grade", "action", "price_target"},
        )

    def _recommendations(self, t, cid, hoy) -> bool:
        try:
            df = t.recommendations
        except Exception:  # noqa: BLE001
            return False
        if df is None or df.empty:
            return False
        filas = []
        for _, r in df.iterrows():
            filas.append(
                {
                    "company_id": cid,
                    "snapshot_date": hoy,
                    "period": str(r.get("period") or "")[:10],
                    "strong_buy": _int(r.get("strongBuy")),
                    "buy": _int(r.get("buy")),
                    "hold": _int(r.get("hold")),
                    "sell": _int(r.get("sell")),
                    "strong_sell": _int(r.get("strongSell")),
                }
            )
        return self._upsert(
            RecommendationTrend,
            filas,
            ["company_id", "snapshot_date", "period"],
            {"strong_buy", "buy", "hold", "sell", "strong_sell"},
        )

    def _shares(self, t, cid) -> bool:
        try:
            s = t.get_shares_full(start="1990-01-01")
        except Exception:  # noqa: BLE001
            return False
        if s is None or len(s) == 0:
            return False
        # Un valor por fecha (el último de cada día)
        filas = {}
        for idx, val in s.items():
            d = _d(idx)
            if d:
                filas[d] = {"company_id": cid, "date": d, "shares": _int(val)}
        return self._upsert(
            SharesHistory,
            list(filas.values()),
            ["company_id", "date"],
            {"shares"},
        )

    def _earnings_dates(self, t, cid) -> bool:
        try:
            df = t.get_earnings_dates(limit=40)
        except Exception:  # noqa: BLE001
            return False
        if df is None or df.empty:
            return False
        filas = {}
        for idx, r in df.iterrows():
            d = _d(idx)
            if not d:
                continue
            filas[d] = {
                "company_id": cid,
                "date": d,
                "eps_estimate": _num(r.get("EPS Estimate")),
                "reported_eps": _num(r.get("Reported EPS")),
                "surprise_pct": _num(r.get("Surprise(%)")),
            }
        return self._upsert(
            EarningsDate,
            list(filas.values()),
            ["company_id", "date"],
            {"eps_estimate", "reported_eps", "surprise_pct"},
        )

    # ── helpers ──────────────────────────────────────

    @staticmethod
    def _targets(tickers) -> list[tuple[str, int]]:
        """Lista de (ticker, company_id) a procesar."""
        session = get_session()
        try:
            sql = (
                "SELECT ticker, id FROM equity.company WHERE is_active = true"
            )
            params = {}
            if tickers:
                sql += " AND ticker = ANY(:tk)"
                params["tk"] = [x.upper() for x in tickers]
            return [(r[0], r[1]) for r in session.execute(text(sql), params)]
        finally:
            session.close()

    def _upsert(self, model, filas, index_elements, update_cols) -> bool:
        """Upsert idempotente troceado. Devuelve si escribió algo.

        Dedup intra-lote por la clave de conflicto (la fuente puede traer
        filas repetidas, p.ej. misma firma/fecha en upgrades).

        Estampa el linaje en el sitio por el que pasan todas las
        secciones del 360°, para no repetirlo siete veces.
        """
        if not filas:
            return False
        dedup = {tuple(f[k] for k in index_elements): f for f in filas}
        filas = list(dedup.values())
        columnas = set(model.__table__.c.keys())
        linaje = {
            k: v for k, v in self.linaje().items() if k in columnas
        }
        if linaje:
            filas = [{**f, **linaje} for f in filas]
            update_cols = set(update_cols) | set(linaje)
        session = get_session()
        try:
            chunk = 3000
            for i in range(0, len(filas), chunk):
                stmt = insert(model).values(filas[i : i + chunk])
                stmt = stmt.on_conflict_do_update(
                    index_elements=index_elements,
                    set_={c: getattr(stmt.excluded, c) for c in update_cols},
                )
                session.execute(stmt)
            session.commit()
            return True
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.warning("Upsert %s falló: %s", model.__tablename__, e)
            return False
        finally:
            session.close()
