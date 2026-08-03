"""Fetcher de Eurostat (JSON-stat): macro mensual/trimestral de la UE.

Eurostat publica en JSON-stat: los valores se indexan por un número
lineal sobre el producto cartesiano de las dimensiones. Este fetcher lo
decodifica y reutiliza los helpers de escritura a macro de
BaseSDMXFetcher. Series de alto valor: HICP mensual, paro, producción
industrial, PIB trimestral.
"""

from urllib.parse import urlencode

from stonks.fetchers.base import logger
from stonks.fetchers.sdmx import _ISO2_TO_3, BaseSDMXFetcher, _period_to_date

# Códigos de país de Eurostat que difieren del ISO-2 estándar.
_ESTAT_ISO = {"EL": "GRC", "UK": "GBR"}


class EurostatFetcher(BaseSDMXFetcher):
    """Descarga indicadores mensuales/trimestrales de Eurostat."""

    SOURCE_NAME = "eurostat"
    BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0"
    # SERIES: (dataset, filtros, code, name, category)
    SERIES = [
        (
            "prc_hicp_manr",
            {"coicop": "CP00", "unit": "RCH_A"},
            "ESTAT_HICP_YOY",
            "HICP inflation rate, annual (Eurostat)",
            "prices",
        ),
        (
            "une_rt_m",
            {"sex": "T", "age": "TOTAL", "unit": "PC_ACT", "s_adj": "SA"},
            "ESTAT_UNEMP_RATE",
            "Unemployment rate (Eurostat)",
            "labor",
        ),
        (
            "sts_inpr_m",
            {"nace_r2": "B-D", "unit": "I21", "s_adj": "SCA"},
            "ESTAT_IND_PROD",
            "Industrial production index (Eurostat)",
            "prices",
        ),
        (
            "namq_10_gdp",
            {"na_item": "B1GQ", "unit": "CLV_PCH_SM", "s_adj": "SCA"},
            "ESTAT_GDP_GROWTH_Q",
            "GDP growth, quarterly (Eurostat)",
            "national_accounts",
        ),
        (
            "sts_trtu_m",
            {"nace_r2": "G47", "unit": "I21", "s_adj": "SCA"},
            "ESTAT_RETAIL_SALES",
            "Retail trade volume index (Eurostat)",
            "consumption",
        ),
        # Gobierno: déficit/superávit (% PIB, anual)
        (
            "gov_10dd_edpt1",
            {
                "unit": "PC_GDP",
                "sector": "S13",
                "na_item": "B9",
            },
            "ESTAT_GOV_DEFICIT",
            "Gov. net lending/borrowing % GDP",
            "fiscal",
        ),
        # Gobierno: gasto total (% PIB, anual)
        (
            "gov_10a_exp",
            {
                "unit": "PC_GDP",
                "cofog99": "TOTAL",
                "sector": "S13",
                "na_item": "TE",
            },
            "ESTAT_GOV_EXPENDITURE",
            "Gov. total expenditure % GDP",
            "fiscal",
        ),
        # Gobierno: ingresos totales (% PIB, anual)
        (
            "gov_10a_main",
            {
                "unit": "PC_GDP",
                "sector": "S13",
                "na_item": "TR",
            },
            "ESTAT_GOV_REVENUE",
            "Gov. total revenue % GDP",
            "fiscal",
        ),
        # Turismo: noches en alojamiento (anual)
        (
            "tour_occ_ninat",
            {"unit": "NR", "c_resid": "TOTAL"},
            "ESTAT_TOURISM_NIGHTS",
            "Tourism nights in accommodation",
            "tourism",
        ),
        # Economía digital: uso internet (% individuos)
        (
            "isoc_ci_ifp_iu",
            {
                "unit": "PC_IND",
                "ind_type": "IND_TOTAL",
                "indic_is": "I_IU3",
            },
            "ESTAT_INTERNET_USE",
            "Internet use last 3 months (%)",
            "digital",
        ),
        # E-commerce (% individuos, 2020+)
        (
            "isoc_ec_ib20",
            {
                "unit": "PC_IND",
                "ind_type": "IND_TOTAL",
                "indic_is": "I_BUY3",
            },
            "ESTAT_ECOMMERCE",
            "E-commerce last 3 months (%)",
            "digital",
        ),
        # Precios vivienda (trimestral, 2015=100)
        (
            "prc_hpi_q",
            {"unit": "I15_Q", "purchase": "TOTAL"},
            "ESTAT_HOUSE_PRICE",
            "House price index (2015=100, Q)",
            "housing",
        ),
        # Producción construcción (mensual, 2015=100)
        (
            "sts_copr_m",
            {
                "unit": "I15",
                "s_adj": "SCA",
                "nace_r2": "F",
            },
            "ESTAT_CONSTRUCTION",
            "Construction production index",
            "production",
        ),
        # Precios al productor (mensual, 2015=100)
        (
            "sts_inppd_m",
            {
                "unit": "I15",
                "s_adj": "NSA",
                "nace_r2": "B-D",
            },
            "ESTAT_PPI",
            "Producer price index (domestic)",
            "prices",
        ),
        # Coste laboral (trimestral, 2020=100)
        (
            "lc_lci_r2_q",
            {
                "unit": "I20",
                "s_adj": "SCA",
                "lcstruct": "D1_D4_MD5",
                "nace_r2": "B-S",
            },
            "ESTAT_LABOUR_COST",
            "Labour cost index (2020=100, Q)",
            "labor",
        ),
    ]

    def fetch(self) -> dict:
        ok = 0
        for dataset, filtros, code, name, category in self.SERIES:
            if self._fetch_dataset(dataset, filtros, code, name, category).get(
                "puntos"
            ):
                ok += 1
        logger.info("eurostat: %d/%d series con datos", ok, len(self.SERIES))
        return {"series": len(self.SERIES), "con_datos": ok}

    def _fetch_dataset(self, dataset, filtros, code, name, category) -> dict:
        run_id = self._start_run(params={"code": code})
        try:
            q = urlencode(
                {"format": "JSON", "sinceTimePeriod": "1990", **filtros}
            )
            self._rate_limit()
            resp = self._session.get(
                f"{self.BASE}/data/{dataset}?{q}", timeout=120
            )
            resp.raise_for_status()
            filas = self._flatten_jsonstat(resp.json())
            n = self._write(code, name, category, filas)
            self._finish_run(run_id, "success", fetched=len(filas), inserted=n)
            return {"code": code, "puntos": n}
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.warning("eurostat %s falló: %s", code, e)
            return {"code": code, "puntos": 0}

    @staticmethod
    def _flatten_jsonstat(d: dict) -> list:
        """JSON-stat → [(país_iso3, fecha, valor)]."""
        ids = d.get("id", [])
        size = d.get("size", [])
        dim = d.get("dimension", {})
        values = d.get("value", {})
        if "geo" not in ids or "time" not in ids or not values:
            return []
        gi, ti = ids.index("geo"), ids.index("time")
        georev = {v: k for k, v in dim["geo"]["category"]["index"].items()}
        timerev = {v: k for k, v in dim["time"]["category"]["index"].items()}
        # Strides row-major: stride[i] = producto de los tamaños a la dcha.
        strides = [1] * len(size)
        for i in range(len(size) - 2, -1, -1):
            strides[i] = strides[i + 1] * size[i + 1]
        out = []
        for kidx, val in values.items():
            n = int(kidx)
            geo = georev.get((n // strides[gi]) % size[gi])
            tcode = timerev.get((n // strides[ti]) % size[ti])
            iso3 = _ESTAT_ISO.get(geo) or _ISO2_TO_3.get(geo)
            dt = _period_to_date(tcode) if tcode else None
            if iso3 and dt and val is not None:
                out.append((iso3, dt, val))
        return out
