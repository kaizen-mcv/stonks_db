"""bronze.api_response (WITS) → trade.flow.

Decodifica el SDMX-JSON de WITS: cada serie es una combinación de
dimensiones (FREQ, REPORTER, PARTNER, PRODUCTCODE, INDICATOR) por índice,
y las observaciones se indexan por la dimensión de tiempo (año).
Idempotente (upsert por reporter/partner/producto/flujo/año).
"""

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.models.bronze import ApiResponse
from stonks.models.meta import DataSource
from stonks.models.trade import Flow
from stonks.transform.base import BaseTransform, logger

_FLOW = {"XPRT-TRD-VL": "X", "MPRT-TRD-VL": "M"}


class TradeTransform(BaseTransform):
    """Vuelca la matriz de comercio de bronze a trade.flow."""

    DOMAIN = "trade"
    TARGET_LAYER = "silver"

    def transform(self) -> None:
        """Procesar el último payload WITS por dataset."""
        run_id = self._start_run()
        session = get_session()
        read = written = 0
        try:
            src_id = self._source_id(session)
            valid = self._valid_countries(session)
            for row in self._latest_datasets(session):
                filas = self._parse(row.payload, valid, src_id)
                read += 1
                written += self._upsert(session, filas)
            self._finish_run(
                run_id,
                "success",
                records_read=read,
                records_written=written,
            )
            logger.info("Trade: %d datasets, %d flujos", read, written)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("TradeTransform falló: %s", e)
        finally:
            session.close()

    @staticmethod
    def _parse(payload, valid, src_id) -> list[dict]:
        """SDMX-JSON WITS → filas de trade.flow."""
        dims = payload.get("structure", {}).get("dimensions", {})
        sdims = dims.get("series", [])
        odims = dims.get("observation", [])
        if not sdims or not odims:
            return []
        pos = {d["id"]: i for i, d in enumerate(sdims)}
        series = payload.get("dataSets", [{}])[0].get("series", {})
        anios = odims[0]["values"]
        filas = []
        for skey, sval in series.items():
            idx = [int(x) for x in skey.split(":")]

            def _val(dim):
                return sdims[pos[dim]]["values"][idx[pos[dim]]]["id"]

            reporter = _val("REPORTER")
            partner = _val("PARTNER")
            product = _val("PRODUCTCODE")
            flow = _FLOW.get(_val("INDICATOR"))
            if flow is None or reporter not in valid:
                continue
            for oidx, obs in sval.get("observations", {}).items():
                value = obs[0] if obs else None
                if value is None:
                    continue
                year = int(anios[int(oidx)]["id"])
                filas.append(
                    {
                        "reporter_code": reporter,
                        "partner_code": partner[:3],
                        "product_code": product[:20],
                        "flow": flow,
                        "period": year,
                        "value_usd_k": value,
                        "source_id": src_id,
                    }
                )
        return filas

    @staticmethod
    def _source_id(session) -> int | None:
        src = session.query(DataSource).filter_by(name="wits").first()
        return src.id if src else None

    @staticmethod
    def _valid_countries(session) -> set[str]:
        rows = session.execute(text("SELECT code FROM ref.country"))
        return {r[0] for r in rows}

    @staticmethod
    def _latest_datasets(session):
        """Último api_response por dataset de WITS."""
        rows = (
            session.query(ApiResponse)
            .filter(ApiResponse.source_name == "wits")
            .order_by(ApiResponse.dataset, ApiResponse.ingested_at.desc())
            .all()
        )
        vistos: set[str] = set()
        out = []
        for r in rows:
            if r.dataset in vistos:
                continue
            vistos.add(r.dataset)
            out.append(r)
        return out

    @staticmethod
    def _upsert(session, filas) -> int:
        if not filas:
            return 0
        # Dedup intra-lote por la clave única.
        dedup = {
            (
                f["reporter_code"],
                f["partner_code"],
                f["product_code"],
                f["flow"],
                f["period"],
            ): f
            for f in filas
        }
        rows = list(dedup.values())
        # Trocear: Postgres limita a 65535 parámetros por sentencia
        # (8 columnas → máx ~8191 filas). Con year=all hay miles.
        chunk = 5000
        for i in range(0, len(rows), chunk):
            stmt = insert(Flow).values(rows[i : i + chunk])
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
        session.commit()
        return len(rows)
