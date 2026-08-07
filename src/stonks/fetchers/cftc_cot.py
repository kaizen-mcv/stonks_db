"""Fetcher del informe COT (Commitments of Traders) de la CFTC.

La CFTC publica cada viernes el posicionamiento agregado de los
operadores en los mercados de futuros estadounidenses, desglosado por
categoria de operador. Es dato publico, gratuito y sin clave, servido
por el portal Socrata del organismo.

La base de datos no tenia ninguna medida de posicionamiento: sabia el
precio de los futuros (`deriv.futures_daily`) pero no quien estaba
comprado o vendido. El COT es la referencia estandar para eso.

Categorias del informe legacy:
- `comm`: coberturistas comerciales (productores y consumidores del
  subyacente). Suelen ir contra la tendencia.
- `noncomm`: especuladores declarantes, tipicamente fondos.
- `nonrept`: operadores por debajo del umbral de declaracion.

Se carga el informe de futuros (`futures only`), con historico
completo desde 1986.
"""

from datetime import date, datetime

import requests
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.deriv import CotContract, CotReport
from stonks.models.meta import DataSource

# Portal Socrata de la CFTC. El recurso 6dca-aqww es el informe legacy
# de futuros, con historico completo desde 1986.
BASE_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
PAGINA = 5000
CHUNK = 2000


class CftcCotFetcher(BaseFetcher):
    """Posicionamiento semanal de futuros declarado a la CFTC."""

    SOURCE_NAME = "cftc_cot"
    DOMAIN = "deriv"
    RATE_LIMIT = 1.0

    def fetch(
        self,
        desde: str | None = None,
        max_paginas: int = 200,
    ) -> dict:
        """Descargar informes COT y cargarlos en deriv.cot_report.

        Args:
            desde: fecha minima (YYYY-MM-DD). Si es None se reanuda
                desde el ultimo informe cargado, y si la tabla esta
                vacia se descarga el historico completo.
            max_paginas: tope de paginas de `PAGINA` registros. Evita
                que un cambio en la fuente provoque una descarga sin
                fin.

        Returns:
            {"informes": N, "contratos": N, "paginas": N}
        """
        session = get_session()
        run_id = self._start_run({"desde": desde})
        src_id = self._ensure_source(session)

        if desde is None:
            desde = self._ultimo_cargado(session)

        contratos: dict[str, dict] = {}
        informes: list[dict] = []
        paginas = 0

        try:
            for pagina in range(max_paginas):
                lote = self._descargar_pagina(pagina * PAGINA, desde)
                if not lote:
                    break
                paginas += 1

                for fila in lote:
                    codigo = (
                        fila.get("cftc_contract_market_code") or ""
                    ).strip()
                    fecha = self._fecha(fila.get("report_date_as_yyyy_mm_dd"))
                    if not codigo or fecha is None:
                        continue

                    contratos.setdefault(
                        codigo,
                        {
                            "code": codigo,
                            "name": self._texto(
                                fila.get("contract_market_name"), 200
                            )
                            or codigo,
                            "exchange": self._texto(
                                fila.get("cftc_market_code"), 20
                            ),
                            "commodity_group": self._texto(
                                fila.get("commodity_group_name"), 60
                            ),
                            "commodity_subgroup": self._texto(
                                fila.get("commodity_subgroup_name"), 80
                            ),
                            "contract_units": self._texto(
                                fila.get("contract_units"), 120
                            ),
                        },
                    )

                    informes.append(
                        {
                            "contract_code": codigo,
                            "report_date": fecha,
                            "open_interest": self._entero(
                                fila.get("open_interest_all")
                            ),
                            "comm_long": self._entero(
                                fila.get("comm_positions_long_all")
                            ),
                            "comm_short": self._entero(
                                fila.get("comm_positions_short_all")
                            ),
                            "noncomm_long": self._entero(
                                fila.get("noncomm_positions_long_all")
                            ),
                            "noncomm_short": self._entero(
                                fila.get("noncomm_positions_short_all")
                            ),
                            "noncomm_spread": self._entero(
                                fila.get("noncomm_postions_spread_all")
                            ),
                            "nonrept_long": self._entero(
                                fila.get("nonrept_positions_long_all")
                            ),
                            "nonrept_short": self._entero(
                                fila.get("nonrept_positions_short_all")
                            ),
                            "traders_total": self._entero(
                                fila.get("traders_tot_all")
                            ),
                            "source_id": src_id,
                        }
                    )

                logger.info(
                    "COT: pagina %d, %d filas acumuladas",
                    pagina + 1,
                    len(informes),
                )
                if len(lote) < PAGINA:
                    break

            # Los contratos primero: cot_report tiene FK contra ellos.
            self._guardar_contratos(session, list(contratos.values()))
            informes = self._deduplicar(informes)
            guardados = self._guardar_informes(session, informes)

            self._finish_run(
                run_id,
                "success",
                fetched=len(informes),
                inserted=guardados,
            )
            logger.info(
                "COT: %d contratos, %d informes cargados",
                len(contratos),
                guardados,
            )
        except Exception as e:
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("COT fallo: %s", e)
            raise
        finally:
            session.close()

        return {
            "informes": len(informes),
            "contratos": len(contratos),
            "paginas": paginas,
        }

    # ── Internos ─────────────────────────────────

    def _descargar_pagina(self, offset: int, desde: str | None) -> list[dict]:
        """Descargar una pagina del recurso Socrata."""
        params = {
            "$limit": PAGINA,
            "$offset": offset,
            "$order": "id",
        }
        if desde:
            params["$where"] = (
                f"report_date_as_yyyy_mm_dd > '{desde}T00:00:00.000'"
            )

        self._rate_limit()
        try:
            resp = self._session.get(BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            datos = resp.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning("COT offset %d: %s", offset, e)
            return []

        return datos if isinstance(datos, list) else []

    @staticmethod
    def _ultimo_cargado(session) -> str | None:
        """Fecha del ultimo informe en la base, para carga incremental."""
        ultima = (
            session.query(CotReport.report_date)
            .order_by(CotReport.report_date.desc())
            .first()
        )
        return ultima[0].isoformat() if ultima else None

    @staticmethod
    def _fecha(valor) -> date | None:
        if not valor:
            return None
        try:
            return datetime.fromisoformat(str(valor)[:19]).date()
        except ValueError:
            return None

    @staticmethod
    def _entero(valor) -> int | None:
        try:
            return int(float(valor)) if valor not in (None, "") else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _texto(valor, largo: int) -> str | None:
        if valor is None:
            return None
        limpio = str(valor).strip()
        return limpio[:largo] if limpio else None

    @staticmethod
    def _deduplicar(informes: list[dict]) -> list[dict]:
        """Quedarse con una fila por contrato y fecha.

        ON CONFLICT no puede resolver duplicados dentro del mismo
        INSERT, asi que la clave se dedupica antes de enviar el lote.
        """
        unicos: dict[tuple, dict] = {}
        for fila in informes:
            unicos[(fila["contract_code"], fila["report_date"])] = fila
        return list(unicos.values())

    @staticmethod
    def _guardar_contratos(session, contratos: list[dict]) -> None:
        """Upsert del catalogo de contratos."""
        for i in range(0, len(contratos), CHUNK):
            trozo = contratos[i : i + CHUNK]
            stmt = insert(CotContract).values(trozo)
            stmt = stmt.on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "name": stmt.excluded.name,
                    "exchange": stmt.excluded.exchange,
                    "commodity_group": stmt.excluded.commodity_group,
                    "commodity_subgroup": stmt.excluded.commodity_subgroup,
                    "contract_units": stmt.excluded.contract_units,
                },
            )
            session.execute(stmt)
        session.commit()

    @staticmethod
    def _guardar_informes(session, informes: list[dict]) -> int:
        """Upsert de los informes semanales."""
        total = 0
        for i in range(0, len(informes), CHUNK):
            trozo = informes[i : i + CHUNK]
            stmt = insert(CotReport).values(trozo)
            stmt = stmt.on_conflict_do_update(
                constraint="cot_report_contract_code_report_date_key",
                set_={
                    "open_interest": stmt.excluded.open_interest,
                    "comm_long": stmt.excluded.comm_long,
                    "comm_short": stmt.excluded.comm_short,
                    "noncomm_long": stmt.excluded.noncomm_long,
                    "noncomm_short": stmt.excluded.noncomm_short,
                    "noncomm_spread": stmt.excluded.noncomm_spread,
                    "nonrept_long": stmt.excluded.nonrept_long,
                    "nonrept_short": stmt.excluded.nonrept_short,
                    "traders_total": stmt.excluded.traders_total,
                },
            )
            total += session.execute(stmt).rowcount or 0
        session.commit()
        return total

    @staticmethod
    def _ensure_source(session) -> int:
        """Registrar la CFTC en meta.data_source si falta."""
        src = session.query(DataSource).filter_by(name="cftc_cot").first()
        if not src:
            src = DataSource(
                name="cftc_cot",
                display_name="CFTC Commitments of Traders",
                base_url=BASE_URL,
                rate_limit_per_second=1.0,
                is_enabled=True,
                notes=(
                    "Posicionamiento semanal en futuros de EE.UU. "
                    "Publico y sin clave, via portal Socrata."
                ),
            )
            session.add(src)
            session.commit()
        return src.id
