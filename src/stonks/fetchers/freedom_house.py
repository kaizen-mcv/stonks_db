"""Fetcher Freedom House — Freedom in the World scores.

Descarga el XLSX de Aggregate Scores (2003-2024) desde
freedomhouse.org (sin auth). Extrae PR rating (1-7),
CL rating (1-7), Total score (0-100) y Status (F/PF/NF)
por país y edición. Parsea XLSX con zipfile+xml.

Los nombres de país se mapean a ISO3 via ref.country.
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
    "https://freedomhouse.org/sites/default/files/"
    "2024-02/"
    "Aggregate_Category_and_Subcategory_Scores"
    "_FIW_2003-2024.xlsx"
)

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# Indicadores a crear
_INDICATORS = [
    (
        "FH_PR",
        "Political Rights rating (Freedom House)",
        "governance",
    ),
    (
        "FH_CL",
        "Civil Liberties rating (Freedom House)",
        "governance",
    ),
    (
        "FH_TOTAL",
        "Freedom in the World total score (Freedom House)",
        "governance",
    ),
]

# Nombres país FH → ISO3 (solo excepciones)
_NAME_MAP = {
    "Bahamas, The": "BHS",
    "Bolivia": "BOL",
    "Bosnia and Herzegovina": "BIH",
    "Brunei": "BRN",
    "Burma": "MMR",
    "Cape Verde": "CPV",
    "Congo (Brazzaville)": "COG",
    "Congo (Kinshasa)": "COD",
    "Cote d'Ivoire": "CIV",
    "Czech Republic": "CZE",
    "East Timor": "TLS",
    "Eswatini": "SWZ",
    "Gambia, The": "GMB",
    "Iran": "IRN",
    "Korea, North": "PRK",
    "Korea, South": "KOR",
    "Laos": "LAO",
    "Micronesia": "FSM",
    "Moldova": "MDA",
    "North Macedonia": "MKD",
    "Russia": "RUS",
    "Saint Kitts and Nevis": "KNA",
    "Saint Lucia": "LCA",
    "Saint Vincent and the Grenadines": "VCT",
    "Sao Tome and Principe": "STP",
    "Slovakia": "SVK",
    "South Korea": "KOR",
    "Syria": "SYR",
    "Taiwan": "TWN",
    "Tanzania": "TZA",
    "Trinidad and Tobago": "TTO",
    "Turkey": "TUR",
    "Turkiye": "TUR",
    "Vatican City": "VAT",
    "Venezuela": "VEN",
    "Vietnam": "VNM",
}


def _parse_xlsx(
    data: bytes,
) -> list[tuple[str, int, int, int, int]]:
    """Extraer (name, edition, pr, cl, total) del XLSX."""
    zf = zipfile.ZipFile(io.BytesIO(data))

    ss_xml = zf.read("xl/sharedStrings.xml")
    root = ET.fromstring(ss_xml)
    strings = [
        "".join(t.text or "" for t in si.findall(f"{{{_NS}}}t"))
        for si in root.findall(f"{{{_NS}}}si")
    ]

    # Buscar la hoja con >1000 filas (datos)
    sheets = sorted(
        n
        for n in zf.namelist()
        if "worksheets/sheet" in n and n.endswith(".xml") and "rels" not in n
    )

    result = []
    for sn in sheets:
        ws_xml = zf.read(sn)
        ws_root = ET.fromstring(ws_xml)
        rows = ws_root.findall(f".//{{{_NS}}}row")
        if len(rows) < 100:
            continue

        # Cabecera
        hcells = _row_values(rows[0], strings)
        name_idx = 0
        ct_idx = next(
            (i for i, h in enumerate(hcells) if h.strip() == "C/T?"),
            None,
        )
        ed_idx = next(
            (i for i, h in enumerate(hcells) if h.strip() == "Edition"),
            None,
        )
        pr_idx = next(
            (i for i, h in enumerate(hcells) if h.strip() == "PR Rating"),
            None,
        )
        cl_idx = next(
            (i for i, h in enumerate(hcells) if h.strip() == "CL Rating"),
            None,
        )
        total_idx = next(
            (i for i, h in enumerate(hcells) if h.strip() == "Total"),
            None,
        )

        if any(
            x is None
            for x in [
                ct_idx,
                ed_idx,
                pr_idx,
                cl_idx,
                total_idx,
            ]
        ):
            continue

        for row in rows[1:]:
            vals = _row_values(row, strings)
            mx = max(
                name_idx,
                ct_idx,
                ed_idx,
                pr_idx,
                cl_idx,
                total_idx,
            )
            if len(vals) <= mx:
                continue
            # Solo países, no territorios
            if vals[ct_idx].strip().lower() != "c":
                continue
            name = vals[name_idx].strip()
            try:
                edition = int(float(vals[ed_idx]))
                pr = int(float(vals[pr_idx]))
                cl = int(float(vals[cl_idx]))
                total = int(float(vals[total_idx]))
            except (ValueError, TypeError):
                continue
            if 2000 <= edition <= 2030:
                result.append((name, edition, pr, cl, total))
        break

    return result


def _row_values(row_el, strings: list[str]) -> list[str]:
    cells = []
    for cell in row_el.findall(f"{{{_NS}}}c"):
        typ = cell.get("t", "")
        val_el = cell.find(f"{{{_NS}}}v")
        val = val_el.text if val_el is not None else ""
        if typ == "s" and val:
            idx = int(val)
            val = strings[idx] if idx < len(strings) else ""
        cells.append(val)
    return cells


class FreedomHouseFetcher(BaseFetcher):
    """Freedom House: PR, CL y Total score anuales."""

    SOURCE_NAME = "freedom_house"
    DOMAIN = "macro"
    RATE_LIMIT = 1.0

    def fetch(self) -> dict:
        run_id = self._start_run(params={"url": _URL})

        resp = _req.get(_URL, timeout=60)
        resp.raise_for_status()
        rows = _parse_xlsx(resp.content)
        logger.info(
            "Freedom House: %d filas parseadas",
            len(rows),
        )

        if not rows:
            self._finish_run(run_id, "success", fetched=0, inserted=0)
            return {"puntos": 0}

        session = get_session()
        try:
            src_id = self._ensure_source(session)

            # Mapa nombre→iso3 desde ref.country
            name_to_iso = {}
            for r in session.execute(
                text("SELECT code, name FROM ref.country")
            ):
                name_to_iso[r[1]] = r[0]
            name_to_iso.update(_NAME_MAP)

            valid_codes = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }

            # Crear los 3 indicadores
            ind_ids = {}
            for code, name, cat in _INDICATORS:
                ind_ids[code] = self._ensure_indicator(
                    session, code, name, cat, src_id
                )

            series_cache: dict[tuple[str, str], int] = {}
            total_inserted = 0

            for ind_code, vals_idx in [
                ("FH_PR", 2),
                ("FH_CL", 3),
                ("FH_TOTAL", 4),
            ]:
                batch = []
                ind_id = ind_ids[ind_code]
                for name, edition, pr, cl, total in rows:
                    iso3 = name_to_iso.get(name)
                    if not iso3 or iso3 not in valid_codes:
                        continue
                    # Edition N analiza año N-1
                    year = edition - 1
                    val = [None, None, pr, cl, total][vals_idx]
                    key = (ind_code, iso3)
                    sid = series_cache.get(key)
                    if sid is None:
                        sid = self._get_series(session, ind_id, iso3)
                        series_cache[key] = sid
                    batch.append(
                        {
                            "series_id": sid,
                            "date": date(year, 12, 31),
                            "value": val,
                            "source_id": src_id,
                        }
                    )

                if batch:
                    stmt = insert(DataPoint).values(batch)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[
                            "series_id",
                            "date",
                        ],
                        set_={"value": stmt.excluded.value},
                    )
                    session.execute(stmt)
                    total_inserted += len(batch)

            session.commit()
            self._finish_run(
                run_id,
                "success",
                fetched=len(rows),
                inserted=total_inserted,
            )
            logger.info(
                "Freedom House: %d puntos insertados",
                total_inserted,
            )
        except Exception as e:
            session.rollback()
            self._finish_run(
                run_id,
                "failed",
                error_log={"msg": str(e)},
            )
            logger.error("Freedom House falló: %s", e)
            raise
        finally:
            session.close()

        return {"puntos": total_inserted}

    def _ensure_source(self, session) -> int:
        src = (
            session.query(DataSource).filter_by(name=self.SOURCE_NAME).first()
        )
        if not src:
            src = DataSource(
                name=self.SOURCE_NAME,
                display_name="Freedom House",
                base_url=(
                    "https://freedomhouse.org/countries/freedom-world/scores"
                ),
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
                frequency="annual",
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
