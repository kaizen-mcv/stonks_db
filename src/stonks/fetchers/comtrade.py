"""Fetcher de UN Comtrade: comercio internacional por producto (HS).

Usa la API v1 (comtradeapi.un.org) con clave gratuita en el header
`Ocp-Apim-Subscription-Key`. Para no agotar el límite de la clave
gratuita, agrega por (reporter, año) pidiendo el desglose por producto
HS de 2 dígitos frente al Mundo (partner=0): así cada país tiene la
estructura de sus exportaciones/importaciones por producto, con pocas
llamadas. Vuelca a `trade.flow` (product_code = HS2, partner='WLD') y
rellena el catálogo `ref.hs_product` con las descripciones devueltas.

Requiere `STONKS_COMTRADE_KEY` en .env (comtradedeveloper.un.org).
"""

import pycountry
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.config import settings
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.meta import DataSource
from stonks.models.trade import Flow, HsProduct

# M49 numérico (Comtrade) → ISO-3, vía pycountry.
_M49_TO_3 = {
    int(c.numeric): c.alpha_3
    for c in pycountry.countries
    if getattr(c, "numeric", None)
}

# Comtrade → letra de flujo interna (X exporta, M importa).
_FLOW = {"X": "X", "M": "M", "RX": "X", "RM": "M"}


class ComtradeFetcher(BaseFetcher):
    """Descarga comercio por producto HS2 de UN Comtrade."""

    SOURCE_NAME = "comtrade"
    DOMAIN = "trade"
    RATE_LIMIT = 1.0
    BASE = "https://comtradeapi.un.org/data/v1/get"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = settings.comtrade_key
        if not self.api_key:
            logger.warning(
                "STONKS_COMTRADE_KEY no configurada "
                "(regístrate en comtradedeveloper.un.org)"
            )

    def fetch(self, years=None, reporters=None, skip_existing=True) -> dict:
        """Descargar HS2 por país y año.

        years: lista de años (por defecto los 5 más recientes cerrados).
        reporters: lista de ISO-3 (por defecto todos los de ref.country
        con equivalente M49).
        skip_existing: saltar países que ya tienen datos HS cargados. El
        plan gratuito limita las llamadas (429), así que reintentar sin
        malgastar llamadas permite completar la cobertura en varias tandas.
        """
        if not self.api_key:
            logger.error("comtrade: sin clave, no se puede descargar")
            return {"reporters": 0, "puntos": 0}
        if years is None:
            years = [2019, 2020, 2021, 2022, 2023]
        reporters = self._resolver_reporters(reporters)
        if skip_existing:
            ya = self._reporters_cargados()
            antes = len(reporters)
            reporters = [r for r in reporters if r[0] not in ya]
            logger.info(
                "comtrade: %d países ya cargados, quedan %d",
                antes - len(reporters),
                len(reporters),
            )
        total = 0
        ok = 0
        for iso3, m49 in reporters:
            n = self._fetch_reporter(iso3, m49, years)
            total += n
            if n:
                ok += 1
        logger.info(
            "comtrade: %d/%d reporters con datos, %d filas",
            ok,
            len(reporters),
            total,
        )
        return {"reporters": ok, "puntos": total}

    @staticmethod
    def _reporters_cargados() -> set[str]:
        """ISO-3 de reporters que ya tienen datos HS (partner=WLD)."""
        session = get_session()
        try:
            return {
                r[0]
                for r in session.execute(
                    text(
                        "SELECT DISTINCT reporter_code FROM trade.flow "
                        "WHERE partner_code = 'WLD'"
                    )
                )
            }
        finally:
            session.close()

    def _resolver_reporters(self, reporters) -> list[tuple[str, int]]:
        """ISO-3 → (iso3, m49) para los países válidos."""
        iso3_to_m49 = {v: k for k, v in _M49_TO_3.items()}
        if reporters is None:
            session = get_session()
            try:
                reporters = [
                    r[0]
                    for r in session.execute(
                        text("SELECT code FROM ref.country")
                    )
                ]
            finally:
                session.close()
        out = []
        for iso3 in reporters:
            m49 = iso3_to_m49.get(iso3)
            if m49 is not None:
                out.append((iso3, m49))
        return out

    def _fetch_reporter(self, iso3, m49, years) -> int:
        """Una llamada por reporter con todos los años y HS2."""
        run_id = self._start_run(params={"reporter": iso3})
        try:
            url = f"{self.BASE}/C/A/HS"
            params = {
                "reporterCode": str(m49),
                "period": ",".join(str(y) for y in years),
                "partnerCode": "0",  # Mundo
                "partner2Code": "0",
                "cmdCode": "AG2",  # todos los HS de 2 dígitos
                "flowCode": "M,X",
                "includeDesc": "true",
            }
            self._rate_limit()
            resp = self._session.get(
                url,
                params=params,
                headers={"Ocp-Apim-Subscription-Key": self.api_key},
                timeout=120,
            )
            resp.raise_for_status()
            filas = resp.json().get("data", [])
            n = self._write(iso3, filas)
            self._finish_run(run_id, "success", fetched=len(filas), inserted=n)
            return n
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.warning("comtrade %s falló: %s", iso3, e)
            return 0

    def _write(self, reporter_iso3, filas) -> int:
        """Volcar filas Comtrade a trade.flow + catálogo HS."""
        if not filas:
            return 0
        session = get_session()
        try:
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            if not src:
                src = DataSource(name=self.SOURCE_NAME)
                session.add(src)
                session.commit()
            src_id = src.id
            filas_flow = {}
            productos = {}
            for r in filas:
                # Comtrade desglosa cada producto por procedimiento
                # aduanero (customsCode) y modo de transporte (motCode);
                # el agregado real es C00 + 0. Sin este filtro se
                # contarían subtotales sueltos (valores erróneos).
                if str(r.get("customsCode", "C00")) != "C00":
                    continue
                if str(r.get("motCode", "0")) not in ("0", "0.0"):
                    continue
                flow = _FLOW.get(r.get("flowCode"))
                cmd = str(r.get("cmdCode", "")).strip()
                period = r.get("refYear") or r.get("period")
                val = r.get("primaryValue")
                if not flow or not cmd or cmd == "TOTAL" or period is None:
                    continue
                # Solo HS2 (2 dígitos); AG2 puede colar 'TOTAL'.
                if not (cmd.isdigit() and len(cmd) == 2):
                    continue
                key = (reporter_iso3, "WLD", cmd, flow, int(period))
                filas_flow[key] = (
                    float(val) / 1000.0 if val is not None else None
                )
                desc = r.get("cmdDesc")
                if desc:
                    productos[cmd] = desc[:500]
            self._upsert_productos(session, productos)
            n = self._upsert_flows(session, filas_flow, src_id)
            session.commit()
            return n
        finally:
            session.close()

    @staticmethod
    def _upsert_productos(session, productos) -> None:
        for code, desc in productos.items():
            stmt = insert(HsProduct).values(
                code=code, description=desc, level=2, parent_code=None
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code"],
                set_={"description": stmt.excluded.description},
            )
            session.execute(stmt)

    @staticmethod
    def _upsert_flows(session, filas_flow, src_id) -> int:
        rows = [
            {
                "reporter_code": rep,
                "partner_code": par,
                "product_code": cmd,
                "flow": flow,
                "period": period,
                "value_usd_k": val,
                "source_id": src_id,
            }
            for (rep, par, cmd, flow, period), val in filas_flow.items()
        ]
        n = 0
        for i in range(0, len(rows), 4000):
            chunk = rows[i : i + 4000]
            stmt = insert(Flow).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    "reporter_code",
                    "partner_code",
                    "product_code",
                    "flow",
                    "period",
                ],
                set_={"value_usd_k": stmt.excluded.value_usd_k},
            )
            session.execute(stmt)
            n += len(chunk)
        return n
