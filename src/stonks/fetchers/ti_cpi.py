"""Fetcher Transparency International — Corruption Perceptions Index.

Descarga el XLSX anual del CDN de TI (sin auth) y extrae la hoja
"Historical Results" con scores 0-100 por país/año desde 2012.
El archivo usa namespace OOXML estricto, se parsea con zipfile+xml.
"""

import io
import xml.etree.ElementTree as ET
import zipfile
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

_URL = (
    "https://images.transparencycdn.org/images/CPI2024-Results-and-trends.xlsx"
)

# Namespaces posibles en OOXML
_NS_CANDIDATES = [
    "http://purl.oclc.org/ooxml/spreadsheetml/main",
    "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
]

_CODE = "TI_CPI"
_NAME = "Corruption Perceptions Index (Transparency Intl)"
_CAT = "governance"


def _parse_xlsx(data: bytes) -> list[tuple[str, int, int]]:
    """Extraer (iso3, año, score) de la hoja Historical."""
    zf = zipfile.ZipFile(io.BytesIO(data))

    # Detectar namespace
    ss_xml = zf.read("xl/sharedStrings.xml")
    ns = None
    for uri in _NS_CANDIDATES:
        root = ET.fromstring(ss_xml)
        sis = root.findall(f"{{{uri}}}si")
        if sis:
            ns = uri
            break
    if ns is None:
        raise ValueError("Namespace OOXML no detectado")

    strings = []
    for si in root.findall(f"{{{ns}}}si"):
        parts = []
        for t in si.iter(f"{{{ns}}}t"):
            parts.append(t.text or "")
        strings.append("".join(parts))

    # Buscar la hoja con datos históricos (sheet5)
    sheets = sorted(
        n
        for n in zf.namelist()
        if "worksheets/sheet" in n and n.endswith(".xml") and "rels" not in n
    )

    result: list[tuple[str, int, int]] = []
    for sn in sheets:
        ws_xml = zf.read(sn)
        ws_root = ET.fromstring(ws_xml)
        rows = ws_root.findall(f".//{{{ns}}}row")
        if len(rows) < 100:
            continue

        # Verificar cabecera: ISO3, Year, CPI score
        header_row = rows[2] if len(rows) > 2 else None
        if header_row is None:
            continue
        hcells = _row_values(header_row, ns, strings)
        if "ISO3" not in hcells or "Year" not in hcells:
            continue

        iso_idx = hcells.index("ISO3")
        year_idx = hcells.index("Year")
        score_idx = next(
            (i for i, h in enumerate(hcells) if "CPI score" in h),
            None,
        )
        if score_idx is None:
            continue

        for row in rows[3:]:
            vals = _row_values(row, ns, strings)
            if len(vals) <= max(iso_idx, year_idx, score_idx):
                continue
            iso3 = vals[iso_idx].strip()
            yr_s = vals[year_idx].strip()
            sc_s = vals[score_idx].strip()
            if not iso3 or not yr_s or not sc_s:
                continue
            try:
                year = int(float(yr_s))
                score = int(float(sc_s))
            except (ValueError, TypeError):
                continue
            if 2000 <= year <= 2030 and 0 <= score <= 100:
                result.append((iso3, year, score))
        break

    return result


def _row_values(row_el, ns: str, strings: list[str]) -> list[str]:
    """Extraer valores de una fila OOXML."""
    cells = []
    for cell in row_el.findall(f"{{{ns}}}c"):
        typ = cell.get("t", "")
        val_el = cell.find(f"{{{ns}}}v")
        val = val_el.text if val_el is not None else ""
        if typ == "s" and val:
            idx = int(val)
            val = strings[idx] if idx < len(strings) else ""
        cells.append(val)
    return cells


class TICPIFetcher(BaseFetcher):
    """Transparency International CPI: score 0-100 anual."""

    SOURCE_NAME = "ti_cpi"
    DOMAIN = "macro"
    RATE_LIMIT = 1.0

    def fetch(self) -> dict:
        run_id = self._start_run(params={"url": _URL})

        resp = _req.get(_URL, timeout=60)
        resp.raise_for_status()
        rows = _parse_xlsx(resp.content)
        logger.info("TI CPI: %d filas parseadas", len(rows))

        if not rows:
            self._finish_run(run_id, "success", fetched=0, inserted=0)
            return {"puntos": 0}

        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }
            ind_id = self._ensure_indicator(session, src_id)
            cache: dict[str, int] = {}
            batch = []
            for iso3, year, score in rows:
                if iso3 not in valid:
                    continue
                sid = cache.get(iso3)
                if sid is None:
                    sid = self._get_series(session, ind_id, iso3)
                    cache[iso3] = sid
                batch.append(
                    {
                        "series_id": sid,
                        "date": date(year, 12, 31),
                        "value": score,
                        "source_id": src_id,
                    }
                )

            if batch:
                stmt = insert(DataPoint).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["series_id", "date"],
                    set_={"value": stmt.excluded.value},
                )
                session.execute(stmt)
            session.commit()
            self._finish_run(
                run_id,
                "success",
                fetched=len(rows),
                inserted=len(batch),
            )
            logger.info(
                "TI CPI: %d puntos insertados",
                len(batch),
            )
        except Exception as e:
            session.rollback()
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("TI CPI falló: %s", e)
            raise
        finally:
            session.close()

        return {"puntos": len(batch)}

    def _ensure_source(self, session) -> int:
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name="Transparency International",
                base_url=("https://www.transparency.org/en/cpi"),
            )
            session.add(src)
            session.commit()
        return src.id

    @staticmethod
    def _ensure_indicator(session, src_id) -> int:
        ind = session.query(Indicator).filter_by(code=_CODE).first()
        if ind is None:
            ind = Indicator(
                code=_CODE,
                name=_NAME[:300],
                category=_CAT,
                frequency="annual",
            )
            session.add(ind)
            session.flush()
            session.add(
                IndicatorSource(
                    indicator_id=ind.id,
                    source_id=src_id,
                    external_code=_CODE,
                    external_name=_NAME[:500],
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
