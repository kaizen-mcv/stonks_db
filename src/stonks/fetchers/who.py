"""Fetcher de WHO GHO (salud global): indicadores por país y año.

API OData sencilla: /api/{indicador} devuelve registros con SpatialDim
(país ISO-3), TimeDim (año) y NumericValue. Reutiliza los helpers de
escritura a macro de BaseSDMXFetcher. Frecuencia anual.
"""

from datetime import date

from stonks.fetchers.base import logger
from stonks.fetchers.sdmx import BaseSDMXFetcher

# (código GHO, nombre, dim1 de sexo o None si no aplica)
_INDICATORS = [
    ("WHOSIS_000001", "Life expectancy at birth (WHO)", "SEX_BTSX"),
    ("WHOSIS_000002", "Healthy life expectancy HALE (WHO)", "SEX_BTSX"),
    ("MDG_0000000001", "Infant mortality rate (WHO)", None),
    ("MDG_0000000007", "Under-five mortality rate (WHO)", None),
    ("MDG_0000000026", "Maternal mortality ratio (WHO)", None),
    ("GHED_CHEGDP_SHA2011", "Health expenditure % of GDP (WHO)", None),
    ("NCDMORT3070", "Prob. dying from NCDs 30-70 (WHO)", "SEX_BTSX"),
    ("NCD_BMI_30C", "Obesity prevalence BMI>=30 (WHO)", "SEX_BTSX"),
    ("SA_0000001688", "Alcohol consumption per capita (WHO)", None),
]


class WHOFetcher(BaseSDMXFetcher):
    """Descarga indicadores de salud de WHO GHO."""

    SOURCE_NAME = "who"
    BASE = "https://ghoapi.azureedge.net/api"
    FREQ = "annual"

    def fetch(self) -> dict:
        ok = 0
        for code, name, dim1 in _INDICATORS:
            if self._fetch_indicator(code, name, dim1).get("puntos"):
                ok += 1
        logger.info("who: %d/%d indicadores con datos", ok, len(_INDICATORS))
        return {"indicadores": len(_INDICATORS), "con_datos": ok}

    def _fetch_indicator(self, code, name, dim1) -> dict:
        run_id = self._start_run(params={"code": code})
        try:
            url = f"{self.BASE}/{code}"
            if dim1:
                url += f"?$filter=Dim1 eq '{dim1}'"
            self._rate_limit()
            resp = self._session.get(url, timeout=120)
            resp.raise_for_status()
            filas = self._parse(resp.json().get("value", []), dim1)
            n = self._write(f"WHO_{code}", name, "health", filas)
            self._finish_run(run_id, "success", fetched=len(filas), inserted=n)
            return {"code": code, "puntos": n}
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.warning("who %s falló: %s", code, e)
            return {"code": code, "puntos": 0}

    @staticmethod
    def _parse(records, dim1) -> list:
        """Registros GHO → [(país_iso3, fecha, valor)]."""
        out = {}
        for r in records:
            if r.get("SpatialDimType") != "COUNTRY":
                continue
            val = r.get("NumericValue")
            iso3 = r.get("SpatialDim")
            year = r.get("TimeDim")
            if val is None or not iso3 or not year:
                continue
            # Si no filtramos por sexo, quedarnos con el total.
            if dim1 is None and r.get("Dim1") not in (None, "", "SEX_BTSX"):
                continue
            try:
                out[(iso3, int(year))] = (
                    iso3,
                    date(int(year), 12, 31),
                    float(val),
                )
            except (ValueError, TypeError):
                continue
        return list(out.values())
