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
