"""Fetcher ECB Statistical Data Warehouse (CSV).

Descarga series monetarias y de tipos de interés de la eurozona
directamente del ECB SDW vía formato CSV (el más fiable).

Complementa al ECBForexFetcher (ecb.py) que solo cubre forex.
Todas las series son eurozona-wide → se registran como indicadores
macro sin country_code (series con country_code='EUZ').
"""

import csv
import io
from datetime import date

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.macro import DataPoint, Indicator, Series
from stonks.models.meta import DataSource

BASE = "https://data-api.ecb.europa.eu/service/data"

# (code, url_path, name, category, frequency)
SERIES = [
    # Agregados monetarios eurozona (índice, dic 2010=100)
    (
        "ECB_M1",
        "BSI/M.U2.Y.V.M10.X.I.U2.2300.Z01.E",
        "M1 Eurozone (index)",
        "monetary",
        "monthly",
    ),
    (
        "ECB_M2",
        "BSI/M.U2.Y.V.M20.X.I.U2.2300.Z01.E",
        "M2 Eurozone (index)",
        "monetary",
        "monthly",
    ),
    (
        "ECB_M3",
        "BSI/M.U2.Y.V.M30.X.I.U2.2300.Z01.E",
        "M3 Eurozone (index)",
        "monetary",
        "monthly",
    ),
    # EURIBOR por tenor (mensual, %)
    (
        "ECB_EURIBOR_1M",
        "FM/M.U2.EUR.RT.MM.EURIBOR1MD_.HSTA",
        "EURIBOR 1-Month",
        "rates",
        "monthly",
    ),
    (
        "ECB_EURIBOR_3M",
        "FM/M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA",
        "EURIBOR 3-Month",
        "rates",
        "monthly",
    ),
    (
        "ECB_EURIBOR_6M",
        "FM/M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA",
        "EURIBOR 6-Month",
        "rates",
        "monthly",
    ),
    (
        "ECB_EURIBOR_1Y",
        "FM/M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA",
        "EURIBOR 12-Month",
        "rates",
        "monthly",
    ),
    # Tipos oficiales BCE
    (
        "ECB_MRR",
        "FM/B.U2.EUR.4F.KR.MRR_FR.LEV",
        "ECB Main Refinancing Rate",
        "rates",
        "daily",
    ),
    (
        "ECB_DFR",
        "FM/B.U2.EUR.4F.KR.DFR.LEV",
        "ECB Deposit Facility Rate",
        "rates",
        "daily",
    ),
    # Tipos bancarios (MIR, mensual, %)
    (
        "ECB_LENDING_CONSUMPTION",
        "MIR/M.U2.B.A2B.A.R.A.2250.EUR.N",
        "Bank lending rate: consumption",
        "rates",
        "monthly",
    ),
    (
        "ECB_LENDING_MORTGAGE",
        "MIR/M.U2.B.A2C.A.R.A.2250.EUR.N",
        "Bank lending rate: mortgages",
        "rates",
        "monthly",
    ),
]

COUNTRY_CODE = "EUZ"


class ECBSDWFetcher(BaseFetcher):
    """Series monetarias y de tipos del ECB SDW."""

    SOURCE_NAME = "ecb"
    DOMAIN = "macro"
    RATE_LIMIT = 1.0

    def fetch(self) -> dict:
        """Descargar todas las series ECB SDW."""
        self._ensure_country()
        run_id = self._start_run(params={"series": len(SERIES)})
        ok = 0
        for code, path, name, cat, freq in SERIES:
            try:
                n = self._fetch_one(code, path, name, cat, freq)
                if n > 0:
                    ok += 1
                logger.info("ECB %s: %d puntos", code, n)
            except Exception as e:  # noqa: BLE001
                logger.warning("ECB %s: %s", code, e)
        self._finish_run(run_id, "success", fetched=ok)
        return {"series": len(SERIES), "con_datos": ok}

    def _fetch_one(self, code, path, name, cat, freq) -> int:
        import requests as _req

        url = f"{BASE}/{path}?format=csvdata&startPeriod=1980"
        self._rate_limit()
        resp = _req.get(url, timeout=60)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        rows = []
        for row in reader:
            val = row.get("OBS_VALUE", "")
            period = row.get("TIME_PERIOD", "")
            if not val or not period:
                continue
            try:
                value = float(val)
            except (ValueError, TypeError):
                continue
            dt = self._parse_period(period)
            if dt:
                rows.append((dt, value))

        if not rows:
            return 0

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            ind_id = self._ensure_indicator(
                session, code, name, cat, src_id, freq
            )
            series_id = self._ensure_series(session, ind_id)
            for dt, val in rows:
                stmt = insert(DataPoint).values(
                    series_id=series_id,
                    date=dt,
                    value=val,
                    source_id=src_id,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["series_id", "date"],
                    set_={"value": stmt.excluded.value},
                )
                session.execute(stmt)
            session.commit()
            return len(rows)
        finally:
            session.close()

    @staticmethod
    def _parse_period(p: str) -> date | None:
        try:
            if len(p) == 10:
                return date.fromisoformat(p)
            if len(p) == 7:
                y, m = p.split("-")
                return date(int(y), int(m), 28)
            if len(p) == 4:
                return date(int(p), 12, 31)
        except (ValueError, TypeError):
            pass
        return None

    def _ensure_source(self, session) -> int:
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(name=self.SOURCE_NAME)
            session.add(src)
            session.commit()
        return src.id

    @staticmethod
    def _ensure_indicator(session, code, name, cat, src_id, freq) -> int:
        from stonks.models.macro import IndicatorSource

        ind = session.query(Indicator).filter_by(code=code).first()
        if ind is None:
            ind = Indicator(
                code=code,
                name=name[:300],
                category=cat,
                frequency=freq,
            )
            session.add(ind)
            session.flush()
            session.add(
                IndicatorSource(
                    indicator_id=ind.id,
                    source_id=src_id,
                    external_code=code,
                    external_name=name[:500],
                )
            )
        return ind.id

    @staticmethod
    def _ensure_series(session, ind_id) -> int:
        s = (
            session.query(Series)
            .filter_by(
                indicator_id=ind_id,
                country_code=COUNTRY_CODE,
                region_code=None,
            )
            .first()
        )
        if s is None:
            s = Series(
                indicator_id=ind_id,
                country_code=COUNTRY_CODE,
                point_count=0,
            )
            session.add(s)
            session.flush()
        return s.id

    @staticmethod
    def _ensure_country():
        """Crear EUZ en ref.country si no existe."""
        session = get_session()
        try:
            exists = session.execute(
                text("SELECT 1 FROM ref.country WHERE code = :c"),
                {"c": COUNTRY_CODE},
            ).scalar()
            if not exists:
                session.execute(
                    text(
                        "INSERT INTO ref.country "
                        "(code, name, region) "
                        "VALUES (:c, :n, :r)"
                    ),
                    {
                        "c": COUNTRY_CODE,
                        "n": "Euro Area",
                        "r": "Europe",
                    },
                )
                session.commit()
                logger.info("Creado ref.country EUZ (Euro Area)")
        finally:
            session.close()
