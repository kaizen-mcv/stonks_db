"""Fetcher de World Bank WITS: comercio bilateral (gratis).

WITS (World Integrated Trade Solution) da estadísticas de comercio en
SDMX-JSON. UN Comtrade requiere clave; WITS no. De momento a nivel
producto 'Total' (matriz bilateral país×país) para exportaciones (X) e
importaciones (M). Aterriza crudo en bronze.api_response.
"""

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.bronze import ApiResponse

BASE = (
    "https://wits.worldbank.org/API/V1/SDMX/V21/datasource/"
    "tradestats-trade/reporter/{rep}/year/{year}/partner/all/"
    "product/Total/indicator/{ind}?format=JSON"
)
INDICATOR = {"X": "XPRT-TRD-VL", "M": "MPRT-TRD-VL"}

# ~90 países. Con year='all' WITS devuelve toda la historia (1989+) en
# una sola llamada por reporter/flujo, así que la cobertura es barata.
DEFAULT_REPORTERS = [
    # Mayores economías
    "usa",
    "chn",
    "deu",
    "jpn",
    "nld",
    "gbr",
    "fra",
    "kor",
    "ita",
    "hkg",
    "mex",
    "can",
    "bel",
    "esp",
    "sgp",
    "che",
    "twn",
    "ind",
    "pol",
    "are",
    "rus",
    "tha",
    "aus",
    "bra",
    "vnm",
    "mys",
    "sau",
    "idn",
    "tur",
    "cze",
    "aut",
    "swe",
    "irl",
    "dnk",
    "hun",
    "zaf",
    "nor",
    "prt",
    "fin",
    "grc",
    "phl",
    "chl",
    "arg",
    "isr",
    "nzl",
    # Europa ampliada
    "rou",
    "bgr",
    "hrv",
    "svk",
    "svn",
    "ltu",
    "lva",
    "est",
    "srb",
    "ukr",
    "isl",
    "lux",
    # Asia ampliada
    "pak",
    "bgd",
    "lka",
    "kaz",
    "uzb",
    "npl",
    "mmr",
    "khm",
    # Oriente Medio
    "qat",
    "kwt",
    "omn",
    "bhr",
    "jor",
    "lbn",
    "irq",
    # África
    "egy",
    "mar",
    "nga",
    "ken",
    "gha",
    "civ",
    "tun",
    "dza",
    "ago",
    "eth",
    # Latinoamérica ampliada
    "col",
    "per",
    "ecu",
    "ury",
    "pry",
    "bol",
    "cri",
    "pan",
    "dom",
    "gtm",
]


class WITSFetcher(BaseFetcher):
    """Descarga la matriz de comercio bilateral de WITS."""

    SOURCE_NAME = "wits"
    DOMAIN = "trade"
    RATE_LIMIT = 0.4

    def fetch_reporter(
        self, reporter: str, flow: str, year: str = "all"
    ) -> dict:
        """Descargar un reporter/flujo (toda la historia) → bronze."""
        dataset = f"{reporter}_{year}_{flow}"
        run_id = self._start_run(params={"dataset": dataset})
        try:
            url = BASE.format(rep=reporter, year=year, ind=INDICATOR[flow])
            data = self._get(url)
            n = len(data.get("dataSets", [{}])[0].get("series", {}))
            self._land(
                dataset,
                {"reporter": reporter, "year": year, "flow": flow},
                data,
                run_id,
            )
            self._finish_run(run_id, "success", fetched=n, inserted=1)
            return {"series": n}
        except Exception as e:  # noqa: BLE001
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.warning("WITS %s falló: %s", dataset, e)
            return {"series": 0}

    def fetch_matrix(
        self,
        reporters: list[str] | None = None,
        year: str = "all",
    ) -> dict:
        """Descargar la matriz para reporters × (X, M), toda la historia."""
        reporters = reporters or DEFAULT_REPORTERS
        total = ok = 0
        for i, rep in enumerate(reporters, 1):
            for flow in ("X", "M"):
                total += 1
                if self.fetch_reporter(rep, flow, year).get("series"):
                    ok += 1
            if i % 10 == 0:
                logger.info("WITS %d/%d reporters", i, len(reporters))
        logger.info("WITS matriz: %d/%d respuestas con datos", ok, total)
        return {"peticiones": total, "con_datos": ok}

    def fetch(self) -> dict:
        """Para el pipeline."""
        return self.fetch_matrix()

    def _land(self, dataset, params, payload, run_id) -> None:
        """Insertar la respuesta cruda en bronze.api_response."""
        session = get_session()
        try:
            session.add(
                ApiResponse(
                    fetch_run_id=run_id,
                    source_name=self.SOURCE_NAME,
                    dataset=dataset,
                    params=params,
                    payload=payload,
                )
            )
            session.commit()
        finally:
            session.close()
