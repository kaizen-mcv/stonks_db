"""Fetcher IMF IFS (International Financial Statistics) — SDMX 3.0 CSV.

Descarga tipos de interés, agregados monetarios y CPI mensuales del
nuevo endpoint api.imf.org (SDMX 3.0). Cobertura global: 190+ países
con series desde 1950 en algunos casos.

Complementa al IMFDataMapperFetcher (imf.py) que solo tiene datos
anuales del WEO. IFS aporta granularidad mensual y series únicas
(lending rate, deposit rate, broad money) no disponibles en BIS/OECD.
"""

import csv
import io
from datetime import date

import requests as _req
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.macro import (
    DataPoint,
    Indicator,
    IndicatorSource,
    Series,
)
from stonks.models.meta import DataSource

BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow"

# (code, dataset, key_filter, name, category)
# key_filter usa * como wildcard de país
IFS_SERIES = [
    (
        "IMF_POLICY_RATE",
        "IMF.STA/MFS_IR/9.0.0",
        "*.MFS166_RT_PT_A_PT.M",
        "Monetary policy rate (IMF IFS)",
        "rates",
    ),
    (
        "IMF_LENDING_RATE",
        "IMF.STA/MFS_IR/9.0.0",
        "*.MFS162_RT_PT_A_PT.M",
        "Lending rate (IMF IFS)",
        "rates",
    ),
    (
        "IMF_DEPOSIT_RATE",
        "IMF.STA/MFS_IR/9.0.0",
        "*.MFS135_RT_PT_A_PT.M",
        "Deposit rate (IMF IFS)",
        "rates",
    ),
    (
        "IMF_DISCOUNT_RATE",
        "IMF.STA/MFS_IR/9.0.0",
        "*.DISR_RT_PT_A_PT.M",
        "Discount rate (IMF IFS)",
        "rates",
    ),
    (
        "IMF_MONEY_MARKET_RATE",
        "IMF.STA/MFS_IR/9.0.0",
        "*.MMRT_RT_PT_A_PT.M",
        "Money market rate (IMF IFS)",
        "rates",
    ),
    (
        "IMF_CPI_YOY",
        "IMF.STA/CPI/5.0.0",
        "*.CPI._T.YOY_PCH_PA_PT.M",
        "CPI inflation YoY% (IMF IFS)",
        "prices",
    ),
    (
        "IMF_BROAD_MONEY",
        "IMF.STA/MFS_MA/10.0.1",
        "*.BM_MAI.XDC.M",
        "Broad money, local currency (IMF IFS)",
        "monetary",
    ),
]


class IMFIFSFetcher(BaseFetcher):
    """IMF IFS: tipos, CPI y monetarios mensuales globales."""

    SOURCE_NAME = "imf_ifs"
    DOMAIN = "macro"
    RATE_LIMIT = 2.0

    def fetch(self) -> dict:
        run_id = self._start_run(params={"series": len(IFS_SERIES)})
        total = 0
        ok = 0
        for code, ds, key, name, cat in IFS_SERIES:
            try:
                n = self._fetch_one(code, ds, key, name, cat)
                total += n
                if n > 0:
                    ok += 1
                logger.info("IMF IFS %s: %d puntos", code, n)
            except Exception as e:  # noqa: BLE001
                logger.warning("IMF IFS %s: %s", code, e)
        self._finish_run(
            run_id,
            "success",
            fetched=total,
            inserted=total,
        )
        return {
            "series": len(IFS_SERIES),
            "con_datos": ok,
            "puntos": total,
        }

    def _fetch_one(self, code, dataset, key, name, cat) -> int:
        url = f"{BASE}/{dataset}/{key}"
        self._rate_limit()
        resp = _req.get(
            url,
            headers={"Accept": "text/csv"},
            timeout=120,
        )
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        rows: list[tuple[str, date, float]] = []
        for row in reader:
            country = row.get("COUNTRY", "")
            period = row.get("TIME_PERIOD", "")
            val = row.get("OBS_VALUE", "")
            if not country or not period or not val:
                continue
            try:
                value = float(val)
            except (ValueError, TypeError):
                continue
            dt = self._parse_period(period)
            if dt:
                rows.append((country, dt, value))

        if not rows:
            return 0

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }
            ind_id = self._ensure_indicator(session, code, name, cat, src_id)
            cache: dict[str, int] = {}
            batch = []
            max_val = 10**14 - 1
            for iso3, dt, val in rows:
                if iso3 not in valid:
                    continue
                if abs(val) >= max_val:
                    continue
                sid = cache.get(iso3)
                if sid is None:
                    sid = self._get_series(session, ind_id, iso3)
                    cache[iso3] = sid
                batch.append(
                    {
                        "series_id": sid,
                        "date": dt,
                        "value": val,
                        "source_id": src_id,
                    }
                )

            # Chunking: PG limita a 65535 parámetros
            CHUNK = 10_000
            for i in range(0, len(batch), CHUNK):
                chunk = batch[i : i + CHUNK]
                stmt = insert(DataPoint).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["series_id", "date"],
                    set_={"value": stmt.excluded.value},
                )
                session.execute(stmt)
            session.commit()
            return len(batch)
        finally:
            session.close()

    @staticmethod
    def _parse_period(p: str) -> date | None:
        """'2026-M05' → date(2026, 5, 28)."""
        try:
            if "-M" in p:
                y, m = p.split("-M")
                return date(int(y), int(m), 28)
            if len(p) == 7 and "-" in p:
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
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name=("IMF International Financial Statistics"),
                base_url="https://data.imf.org/",
            )
            session.add(src)
            session.commit()
        return src.id

    @staticmethod
    def _ensure_indicator(session, code, name, cat, src_id) -> int:
        ind = session.query(Indicator).filter_by(code=code).first()
        if ind is None:
            ind = Indicator(
                code=code,
                name=name[:300],
                category=cat,
                frequency="monthly",
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
    def _get_series(session, ind_id, iso3) -> int:
        s = (
            session.query(Series)
            .filter_by(
                indicator_id=ind_id,
                country_code=iso3,
                region_code=None,
            )
            .first()
        )
        if s is None:
            s = Series(
                indicator_id=ind_id,
                country_code=iso3,
                point_count=0,
            )
            session.add(s)
            session.flush()
        return s.id
