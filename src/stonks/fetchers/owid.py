"""Fetcher de Our World in Data (OWID): energía (sin clave).

OWID publica CSVs curados. energy-data.csv trae, por país y año, decenas
de columnas por fuente (coal/oil/gas/nuclear/renovables...). Fundimos las
columnas absolutas (TWh) a filas energy.balance (país × fuente × flujo).
Escribe directo a silver (como world_bank), con auditoría en fetch_run.
"""

import csv
import io

from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.bronze import ApiResponse
from stonks.models.energy import Balance
from stonks.models.macro import Indicator, IndicatorSource
from stonks.models.meta import DataSource

ENERGY_CSV = (
    "https://raw.githubusercontent.com/owid/energy-data/master/"
    "owid-energy-data.csv"
)
CO2_CSV = (
    "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
)

# Columna OWID CO2 → (code macro, nombre, unidad). Categoría: environment.
CO2_MAP = {
    "co2": ("OWID_CO2", "CO2 emissions", "Mt"),
    "co2_per_capita": ("OWID_CO2_PC", "CO2 per capita", "t"),
    "share_global_co2": ("OWID_CO2_SHARE", "Share of global CO2", "%"),
    "total_ghg": ("OWID_GHG", "Total greenhouse gases", "Mt CO2e"),
    "methane": ("OWID_METHANE", "Methane emissions", "Mt CO2e"),
}

# Columna OWID → (producto, flujo). Solo columnas absolutas en TWh.
COLUMN_MAP = {
    "coal_consumption": ("coal", "consumption"),
    "coal_production": ("coal", "production"),
    "coal_electricity": ("coal", "electricity"),
    "oil_consumption": ("oil", "consumption"),
    "oil_production": ("oil", "production"),
    "oil_electricity": ("oil", "electricity"),
    "gas_consumption": ("gas", "consumption"),
    "gas_production": ("gas", "production"),
    "gas_electricity": ("gas", "electricity"),
    "nuclear_consumption": ("nuclear", "consumption"),
    "nuclear_electricity": ("nuclear", "electricity"),
    "hydro_consumption": ("hydro", "consumption"),
    "hydro_electricity": ("hydro", "electricity"),
    "solar_consumption": ("solar", "consumption"),
    "solar_electricity": ("solar", "electricity"),
    "wind_consumption": ("wind", "consumption"),
    "wind_electricity": ("wind", "electricity"),
    "biofuel_consumption": ("biofuel", "consumption"),
    "renewables_consumption": ("renewables", "consumption"),
    "renewables_electricity": ("renewables", "electricity"),
    "fossil_fuel_consumption": ("fossil", "consumption"),
    "fossil_electricity": ("fossil", "electricity"),
    "low_carbon_consumption": ("low_carbon", "consumption"),
    "low_carbon_electricity": ("low_carbon", "electricity"),
    "primary_energy_consumption": ("primary_energy", "consumption"),
    "electricity_generation": ("total", "electricity"),
    "electricity_demand": ("total", "demand"),
}


class OWIDEnergyFetcher(BaseFetcher):
    """Descarga el balance energético mundial de OWID."""

    SOURCE_NAME = "owid"
    DOMAIN = "energy"
    RATE_LIMIT = 1.0

    def fetch(self) -> dict:
        """Descargar y volcar el balance energético a energy.balance."""
        run_id = self._start_run(params={"dataset": "energy"})
        stats = {"fetched": 0, "inserted": 0}
        try:
            self._rate_limit()
            resp = self._session.get(ENERGY_CSV, timeout=120)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            src_id = self._source_id()
            valid = self._valid_countries()
            cols = [c for c in COLUMN_MAP if c in (reader.fieldnames or [])]
            batch: list[dict] = []
            for row in reader:
                iso = (row.get("iso_code") or "").strip()
                if iso not in valid or not row.get("year"):
                    continue
                year = int(row["year"])
                for col in cols:
                    val = row.get(col)
                    if val in (None, ""):
                        continue
                    prod, flow = COLUMN_MAP[col]
                    batch.append(
                        {
                            "country_code": iso,
                            "product_code": prod,
                            "flow": flow,
                            "period": year,
                            "value": float(val),
                            "unit": "TWh",
                            "source_id": src_id,
                        }
                    )
                    stats["fetched"] += 1
                if len(batch) >= 5000:
                    stats["inserted"] += self._flush(batch)
                    batch = []
            stats["inserted"] += self._flush(batch)
            self._finish_run(run_id, "success", **stats)
            logger.info("OWID energía: %d filas", stats["inserted"])
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("OWID energía falló: %s", e)
        return stats

    def fetch_co2(self) -> dict:
        """Emisiones (medio ambiente) → bronze con forma IMF.

        Aterriza cada indicador como {values:{code:{iso:{año:val}}}} para
        que MacroIndicatorsTransform('owid') lo vuelque a macro igual que
        el IMF. Registra los indicadores (categoría environment).
        """
        run_id = self._start_run(params={"dataset": "co2"})
        try:
            self._rate_limit()
            resp = self._session.get(CO2_CSV, timeout=120)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            valid = self._valid_countries()
            cols = [c for c in CO2_MAP if c in (reader.fieldnames or [])]
            # {code: {iso: {year: val}}}
            data: dict[str, dict] = {CO2_MAP[c][0]: {} for c in cols}
            for row in reader:
                iso = (row.get("iso_code") or "").strip()
                if iso not in valid or not row.get("year"):
                    continue
                year = row["year"]
                for c in cols:
                    val = row.get(c)
                    if val in (None, ""):
                        continue
                    code = CO2_MAP[c][0]
                    data[code].setdefault(iso, {})[year] = float(val)
            self._register_co2()
            n = self._land_co2(data, run_id)
            self._finish_run(run_id, "success", fetched=len(cols), inserted=n)
            logger.info("OWID CO2: %d indicadores aterrizados", n)
            return {"indicadores": n}
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("OWID CO2 falló: %s", e)
            return {}

    def _register_co2(self) -> None:
        """Registrar los indicadores de CO2 en macro (categoría env.)."""
        session = get_session()
        try:
            src_id = self._source_id()
            for _col, (code, name, unit) in CO2_MAP.items():
                ind = session.query(Indicator).filter_by(code=code).first()
                if ind is None:
                    ind = Indicator(
                        code=code,
                        name=name,
                        category="environment",
                        unit=unit,
                        frequency="annual",
                    )
                    session.add(ind)
                    session.flush()
                if src_id and not (
                    session.query(IndicatorSource)
                    .filter_by(indicator_id=ind.id, source_id=src_id)
                    .first()
                ):
                    session.add(
                        IndicatorSource(
                            indicator_id=ind.id,
                            source_id=src_id,
                            external_code=code,
                            external_name=name,
                        )
                    )
            session.commit()
        finally:
            session.close()

    def _land_co2(self, data: dict, run_id: int) -> int:
        """Aterrizar cada indicador CO2 en bronze con forma IMF."""
        session = get_session()
        n = 0
        try:
            for code, valores in data.items():
                if not valores:
                    continue
                session.add(
                    ApiResponse(
                        fetch_run_id=run_id,
                        source_name=self.SOURCE_NAME,
                        dataset=code,
                        params={"indicator": code},
                        payload={"values": {code: valores}},
                    )
                )
                n += 1
            session.commit()
        finally:
            session.close()
        return n

    def _source_id(self) -> int | None:
        session = get_session()
        try:
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            return src.id if src else None
        finally:
            session.close()

    @staticmethod
    def _valid_countries() -> set[str]:
        from sqlalchemy import text

        session = get_session()
        try:
            rows = session.execute(text("SELECT code FROM ref.country"))
            return {r[0] for r in rows}
        finally:
            session.close()

    @staticmethod
    def _flush(batch: list[dict]) -> int:
        """Upsert idempotente de un lote en energy.balance."""
        if not batch:
            return 0
        session = get_session()
        try:
            stmt = insert(Balance).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    "country_code",
                    "product_code",
                    "flow",
                    "period",
                ],
                set_={"value": stmt.excluded.value},
            )
            session.execute(stmt)
            session.commit()
            return len(batch)
        finally:
            session.close()
