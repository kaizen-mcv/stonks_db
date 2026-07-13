"""bronze.api_response → macro.series / macro.data_point.

Normaliza las respuestas crudas de las fuentes macro a series temporales
país × indicador × fecha. El mapeo código-externo → indicador se resuelve
por macro.indicator_source. Idempotente (upsert por (series, date)).

Soporta la forma del IMF DataMapper: payload['values'][code][pais][año].
Otras fuentes se pueden añadir con un adaptador de forma.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.models.bronze import ApiResponse
from stonks.models.macro import DataPoint, IndicatorSource, Series
from stonks.models.meta import DataSource
from stonks.transform.base import BaseTransform, logger


class MacroIndicatorsTransform(BaseTransform):
    """Vuelca respuestas macro de bronze a la capa silver."""

    DOMAIN = "macro_indicators"
    TARGET_LAYER = "silver"

    def transform(self, source_name: str = "imf") -> None:
        """Procesar el último payload por dataset de una fuente."""
        run_id = self._start_run(params={"source": source_name})
        session = get_session()
        read = written = 0
        try:
            src_id = self._source_id(session, source_name)
            code_to_ind = self._code_to_indicator(session, src_id)
            valid_countries = self._valid_countries(session)
            for row in self._latest_by_dataset(session, source_name):
                ind_id = code_to_ind.get(row.dataset)
                if ind_id is None:
                    continue
                read += 1
                written += self._volcar_imf(
                    row.payload,
                    row.dataset,
                    ind_id,
                    src_id,
                    valid_countries,
                )
            self._finish_run(
                run_id,
                "success",
                records_read=read,
                records_written=written,
            )
            logger.info(
                "Macro %s: %d indicadores, %d puntos",
                source_name,
                read,
                written,
            )
        except Exception as e:  # noqa: BLE001
            session.rollback()
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("MacroIndicatorsTransform falló: %s", e)
        finally:
            session.close()

    def _volcar_imf(
        self, payload, code, ind_id, src_id, valid_countries
    ) -> int:
        """Volcar un indicador IMF (values[code][pais][año])."""
        values = (payload or {}).get("values", {}).get(code, {})
        session = get_session()
        n = 0
        try:
            for geo, serie in values.items():
                es_pais = geo in valid_countries
                series_id = self._get_or_create_series(
                    session, ind_id, geo, es_pais
                )
                filas = []
                for anio, val in serie.items():
                    if val is None:
                        continue
                    try:
                        dt = date(int(anio), 12, 31)
                    except (ValueError, TypeError):
                        continue
                    filas.append(
                        {
                            "series_id": series_id,
                            "date": dt,
                            "value": val,
                            "source_id": src_id,
                        }
                    )
                n += self._upsert_points(session, filas)
                self._touch_series(session, series_id, filas)
            session.commit()
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.warning("Indicador %s falló: %s", code, e)
        finally:
            session.close()
        return n

    # ── helpers ──────────────────────────────────────

    @staticmethod
    def _source_id(session, source_name) -> int | None:
        src = session.query(DataSource).filter_by(name=source_name).first()
        return src.id if src else None

    @staticmethod
    def _code_to_indicator(session, src_id) -> dict[str, int]:
        if src_id is None:
            return {}
        rows = (
            session.query(
                IndicatorSource.external_code,
                IndicatorSource.indicator_id,
            )
            .filter_by(source_id=src_id)
            .all()
        )
        return {code: ind for code, ind in rows}

    @staticmethod
    def _valid_countries(session) -> set[str]:
        rows = session.execute(text("SELECT code FROM ref.country"))
        return {r[0] for r in rows}

    @staticmethod
    def _latest_by_dataset(session, source_name):
        """Último api_response por dataset (excluye el catálogo)."""
        rows = (
            session.query(ApiResponse)
            .filter(
                ApiResponse.source_name == source_name,
                ApiResponse.dataset != "indicators",
            )
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
    def _get_or_create_series(session, ind_id, geo, es_pais) -> int:
        """Serie (indicador, país) o (indicador, región)."""
        country = geo if es_pais else None
        region = None if es_pais else geo
        q = session.query(Series).filter_by(
            indicator_id=ind_id, country_code=country, region_code=region
        )
        s = q.first()
        if s is None:
            s = Series(
                indicator_id=ind_id,
                country_code=country,
                region_code=region,
                point_count=0,
            )
            session.add(s)
            session.flush()
        return s.id

    @staticmethod
    def _upsert_points(session, filas) -> int:
        if not filas:
            return 0
        stmt = insert(DataPoint).values(filas)
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_id", "date"],
            set_={
                "value": stmt.excluded.value,
                "source_id": stmt.excluded.source_id,
            },
        )
        session.execute(stmt)
        return len(filas)

    @staticmethod
    def _touch_series(session, series_id, filas) -> None:
        """Actualizar last_date/last_value/point_count de la serie."""
        if not filas:
            return
        ultimo = max(filas, key=lambda f: f["date"])
        session.execute(
            text(
                "UPDATE macro.series SET last_date = :d, last_value = :v, "
                "point_count = (SELECT count(*) FROM macro.data_point "
                "               WHERE series_id = :s) WHERE id = :s"
            ),
            {"d": ultimo["date"], "v": ultimo["value"], "s": series_id},
        )
