"""Parser SDMX-JSON compartido (OECD, BIS, ILO).

Los tres organismos publican en SDMX-JSON: un formato verboso donde las
observaciones se indexan por combinaciones de dimensiones. Este módulo
aplana esa estructura y escribe series país×indicador×fecha directamente
en `macro` (registrando el indicador), reutilizando el motor de series.

Cada organismo hereda BaseSDMXFetcher y aporta su BASE + una lista SERIES
de indicadores de alto valor (dataflow, clave, código, nombre, categoría).
"""

from datetime import date

import pycountry
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.macro import DataPoint, Indicator, IndicatorSource, Series
from stonks.models.meta import DataSource

_ISO2_TO_3 = {
    c.alpha_2: c.alpha_3 for c in pycountry.countries if hasattr(c, "alpha_2")
}


def _period_to_date(p: str) -> date | None:
    """'2026', '2026-04', '2026-Q2' → fecha (fin de periodo)."""
    try:
        if "-Q" in p:
            y, q = p.split("-Q")
            return date(int(y), int(q) * 3, 28)
        if "-" in p:
            y, m = p.split("-")[:2]
            return date(int(y), int(m), 28)
        return date(int(p), 12, 31)
    except (ValueError, TypeError):
        return None


class BaseSDMXFetcher(BaseFetcher):
    """Base para fetchers SDMX-JSON. Subclases: BASE, SERIES."""

    DOMAIN = "macro"
    RATE_LIMIT = 1.0
    BASE = ""
    # Plantilla de ruta de datos (varía por organismo).
    DATA_PATH = "/data/{df}/{key}"
    COUNTRY_DIM = "REF_AREA"
    ISO2 = False  # si el país viene en ISO-2 (BIS) hay que convertir
    START_PERIOD = "1990"  # acota la consulta (evita 500 por volumen)
    FREQ = "monthly"  # frecuencia de las series (para el catálogo)
    # SERIES: (dataflow_ref, key, code, name, category)
    SERIES: list[tuple] = []

    def fetch(self) -> dict:
        """Descargar todas las series configuradas."""
        ok = 0
        for row in self.SERIES:
            if self.fetch_series(*row).get("puntos"):
                ok += 1
        logger.info(
            "%s: %d/%d series con datos",
            self.SOURCE_NAME,
            ok,
            len(self.SERIES),
        )
        return {"series": len(self.SERIES), "con_datos": ok}

    def fetch_series(self, dataflow, key, code, name, category) -> dict:
        """Descargar una serie SDMX y volcarla a macro."""
        run_id = self._start_run(params={"code": code})
        try:
            path = self.DATA_PATH.format(df=dataflow, key=key)
            url = (
                f"{self.BASE}{path}?dimensionAtObservation=AllDimensions"
                f"&startPeriod={self.START_PERIOD}"
            )
            data = self._sdmx_get(url)
            filas = self._flatten(data)
            n = self._write(code, name, category, filas)
            self._finish_run(run_id, "success", fetched=len(filas), inserted=n)
            return {"code": code, "puntos": n}
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.warning("%s %s falló: %s", self.SOURCE_NAME, code, e)
            return {"code": code, "puntos": 0}

    def _sdmx_get(self, url: str) -> dict:
        self._rate_limit()
        resp = self._session.get(
            url,
            headers={"Accept": "application/vnd.sdmx.data+json"},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    def _flatten(self, data: dict) -> list[tuple[str, date, float]]:
        """SDMX-JSON → lista de (país_iso3, fecha, valor)."""
        d = data.get("data", data)
        struct = d.get("structure") or (d.get("structures") or [None])[0]
        if not struct:
            return []
        dims = struct["dimensions"]["observation"]
        pos = {dim["id"]: i for i, dim in enumerate(dims)}
        cpos = pos.get(self.COUNTRY_DIM)
        if cpos is None:
            cpos = pos.get("BORROWERS_CTY")
        tpos = pos.get("TIME_PERIOD")
        if cpos is None or tpos is None:
            return []
        obs = d.get("dataSets", [{}])[0].get("observations", {})
        out = []
        for k, v in obs.items():
            idx = [int(i) for i in k.split(":")]
            geo = dims[cpos]["values"][idx[cpos]]["id"]
            iso3 = _ISO2_TO_3.get(geo) if self.ISO2 else geo
            if iso3 is None:
                continue
            dt = _period_to_date(dims[tpos]["values"][idx[tpos]]["id"])
            val = v[0] if v else None
            if dt and val is not None:
                out.append((iso3, dt, val))
        return out

    def _write(self, code, name, category, filas) -> int:
        """Registrar indicador y volcar puntos a macro."""
        if not filas:
            return 0
        session = get_session()
        try:
            src_id = self._ensure_source(session)
            valid = {
                r[0]
                for r in session.execute(text("SELECT code FROM ref.country"))
            }
            ind_id = self._ensure_indicator(
                session, code, name, category, src_id, self.FREQ
            )
            series_cache: dict[str, int] = {}
            n = 0
            for iso3, dt, val in filas:
                if iso3 not in valid:
                    continue
                sid = series_cache.get(iso3)
                if sid is None:
                    sid = self._get_series(session, ind_id, iso3)
                    series_cache[iso3] = sid
                stmt = insert(DataPoint).values(
                    series_id=sid, date=dt, value=val, source_id=src_id
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["series_id", "date"],
                    set_={"value": stmt.excluded.value},
                )
                session.execute(stmt)
                n += 1
            session.commit()
            return n
        finally:
            session.close()

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
    def _ensure_indicator(
        session, code, name, category, src_id, freq="monthly"
    ) -> int:
        ind = session.query(Indicator).filter_by(code=code).first()
        if ind is None:
            ind = Indicator(
                code=code,
                name=name[:300],
                category=category,
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
    def _get_series(session, ind_id, iso3) -> int:
        s = (
            session.query(Series)
            .filter_by(
                indicator_id=ind_id, country_code=iso3, region_code=None
            )
            .first()
        )
        if s is None:
            s = Series(indicator_id=ind_id, country_code=iso3, point_count=0)
            session.add(s)
            session.flush()
        return s.id


class ILOFetcher(BaseSDMXFetcher):
    """Organización Internacional del Trabajo (ILOSTAT, SDMX).

    Series anuales (total ambos sexos, 15+ años) para ~275 áreas.
    Clave: REF_AREA.FREQ.MEASURE.SEX.AGE → constreñimos SEX/AGE al total.
    """

    SOURCE_NAME = "ilostat"
    BASE = "https://sdmx.ilo.org"
    DATA_PATH = "/rest/data/{df}/{key}"
    START_PERIOD = "2000"
    FREQ = "annual"
    SERIES = [
        (
            "ILO,DF_UNE_2EAP_SEX_AGE_RT,1.0",
            "...SEX_T.AGE_YTHADULT_YGE15",
            "ILO_UNEMPLOYMENT",
            "Unemployment rate (ILO)",
            "labor",
        ),
        (
            "ILO,DF_EAP_DWAP_SEX_AGE_RT,1.0",
            "...SEX_T.AGE_YTHADULT_YGE15",
            "ILO_PARTICIPATION",
            "Labour force participation rate (ILO)",
            "labor",
        ),
        (
            "ILO,DF_EMP_TEMP_SEX_AGE_NB,1.0",
            "...SEX_T.AGE_YTHADULT_YGE15",
            "ILO_EMPLOYMENT",
            "Employment total (ILO, thousands)",
            "labor",
        ),
    ]


class OECDFetcher(BaseSDMXFetcher):
    """OECD (SDMX): precios mensuales, producción, indicadores adelantados.

    CPI mensual interanual para todos los países OECD. Clave con FREQ=M.
    """

    SOURCE_NAME = "oecd"
    BASE = "https://sdmx.oecd.org/public/rest"
    START_PERIOD = "1990-01"
    FREQ = "monthly"
    SERIES = [
        (
            "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0",
            ".M.N.CPI.PA._T.N.GY",
            "OECD_CPI_YOY",
            "CPI inflation YoY, monthly (OECD)",
            "prices",
        ),
        # KEI (Key Economic Indicators) — 7 posiciones de clave
        (
            "OECD.SDD.STES,DSD_KEI@DF_KEI,4.0",
            ".M.LI....",
            "OECD_CLI",
            "Composite Leading Indicator (OECD)",
            "leading",
        ),
        (
            "OECD.SDD.STES,DSD_KEI@DF_KEI,4.0",
            ".M.CCICP....",
            "OECD_CONSUMER_CONF",
            "Consumer confidence (OECD)",
            "sentiment",
        ),
        (
            "OECD.SDD.STES,DSD_KEI@DF_KEI,4.0",
            ".M.BCICP....",
            "OECD_BUSINESS_CONF",
            "Business confidence (OECD)",
            "sentiment",
        ),
        (
            "OECD.SDD.STES,DSD_KEI@DF_KEI,4.0",
            ".M.PRVM....",
            "OECD_IND_PROD",
            "Industrial production volume (OECD)",
            "production",
        ),
        (
            "OECD.SDD.STES,DSD_KEI@DF_KEI,4.0",
            ".M.TOVM....",
            "OECD_RETAIL_VOL",
            "Retail trade volume (OECD)",
            "consumption",
        ),
        # Precios vivienda (trimestral)
        (
            "OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,1.0",
            ".Q.RHP.IX",
            "OECD_HOUSE_PRICE_REAL",
            "Real house price index (OECD)",
            "housing",
        ),
        # Productividad laboral
        (
            "OECD.SDD.TPS,DSD_PDB@DF_PDB,2.0",
            ".A.GDPHRS._T.USD_PPP_H.LR.N._Z.PPP",
            "OECD_GDP_PER_HOUR",
            "GDP per hour worked (OECD, PPP USD)",
            "productivity",
        ),
        # Gasto social total (% PIB)
        (
            "OECD.ELS.SPD,DSD_SOCX_AGG@DF_SOCX_AGG,1.0",
            ".A.SOCX.PT_B1GQ.ES10._T._T._Z",
            "OECD_SOCIAL_SPENDING",
            "Public social spending % GDP (OECD)",
            "fiscal",
        ),
        # Pensiones (% PIB)
        (
            "OECD.ELS.SPD,DSD_SOCX_AGG@DF_SOCX_AGG,1.0",
            ".A.SOCX.PT_B1GQ.ES10._T.TP01._Z",
            "OECD_PENSION_SPEND",
            "Pension spending % GDP (OECD)",
            "fiscal",
        ),
        # I+D total (% PIB)
        (
            "OECD.STI.STP,DSD_MSTI@DF_MSTI,1.3",
            ".A.G.PT_B1GQ._Z._Z",
            "OECD_RD_GDP",
            "R&D expenditure % GDP (OECD)",
            "innovation",
        ),
        # Gini (desigualdad ingreso)
        (
            "OECD.WISE.INE,DSD_WISE_IDD@DF_IDD,1.0",
            ".A.INC_DISP_GINI._Z.0_TO_1._T.METH2012.D_CUR._Z",
            "OECD_GINI",
            "Gini coefficient (OECD)",
            "inequality",
        ),
    ]


class BISFetcher(BaseSDMXFetcher):
    """Banco de Pagos Internacionales: tipos, crédito, inmobiliario."""

    SOURCE_NAME = "bis"
    BASE = "https://stats.bis.org/api/v2"
    DATA_PATH = "/data/dataflow/{df}/{key}"
    ISO2 = True
    SERIES = [
        (
            "BIS/WS_CBPOL/1.0",
            "M.",
            "BIS_POLICY_RATE",
            "Central bank policy rate",
            "financial",
        ),
        (
            "BIS/WS_LONG_CPI/1.0",
            "M...",
            "BIS_CPI",
            "Consumer prices (BIS)",
            "prices",
        ),
        (
            "BIS/WS_CREDIT_GAP/1.0",
            "Q...",
            "BIS_CREDIT_GAP",
            "Credit-to-GDP gap",
            "financial",
        ),
        (
            "BIS/WS_EER/1.0",
            "M.N.B.",
            "BIS_REER",
            "Real effective exchange rate",
            "financial",
        ),
        (
            "BIS/WS_SPP/1.0",
            "Q..R.771",
            "BIS_HOUSE_PRICE",
            "Residential property prices YoY%",
            "housing",
        ),
        (
            "BIS/WS_TC/2.0",
            "Q..P.A.M.770.A",
            "BIS_CREDIT_GDP",
            "Credit to private sector % GDP",
            "financial",
        ),
        (
            "BIS/WS_DSR/1.0",
            "Q..P",
            "BIS_DEBT_SERVICE",
            "Private sector debt service ratio",
            "financial",
        ),
    ]
