"""Fetcher de WID.world (World Inequality Database): renta y riqueza.

WID solo publica el dataset completo como un zip (~883 MB) que contiene
un CSV por país (WID_data_XX.csv, separado por ';'). Este fetcher lo baja
una vez a caché, recorre los ficheros de país y extrae un puñado de
variables de alto valor (cuotas del top 1%/10% de renta y riqueza, Gini),
volcándolas a `macro` (categoría wealth). Frecuencia anual.

Códigos de variable WID: concepto(6)+población(1)+edad(3), p.ej.
`sptincj992` = cuota de renta nacional antes de impuestos, adultos.
La columna `percentile` selecciona el tramo: p99p100=top1%, p90p100=top10%,
p0p100=total (para el Gini).
"""

import csv
import io
import zipfile
from datetime import date
from pathlib import Path

import pycountry

from stonks.fetchers.base import logger
from stonks.fetchers.sdmx import BaseSDMXFetcher

_BULK_URL = "https://wid.world/bulk_download/wid_all_data.zip"
_CACHE = Path("data/cache/wid_all_data.zip")

# ISO-2 → ISO-3 para mapear el código de área de WID a ref.country.
_ISO2_TO_3 = {
    c.alpha_2: c.alpha_3 for c in pycountry.countries if hasattr(c, "alpha_2")
}

# (variable, percentil, código indicador, nombre)
_TARGETS = [
    ("sptincj992", "p99p100", "WID_INC_TOP1",
     "Top 1% pre-tax national income share (WID)"),
    ("sptincj992", "p90p100", "WID_INC_TOP10",
     "Top 10% pre-tax national income share (WID)"),
    ("sptincj992", "p0p50", "WID_INC_BOT50",
     "Bottom 50% pre-tax national income share (WID)"),
    ("shwealj992", "p99p100", "WID_WEALTH_TOP1",
     "Top 1% net personal wealth share (WID)"),
    ("shwealj992", "p90p100", "WID_WEALTH_TOP10",
     "Top 10% net personal wealth share (WID)"),
    ("gptincj992", "p0p100", "WID_INC_GINI",
     "Gini of pre-tax national income (WID)"),
]


class WIDFetcher(BaseSDMXFetcher):
    """Descarga cuotas de renta/riqueza y Gini de WID.world."""

    SOURCE_NAME = "wid"
    FREQ = "annual"

    def fetch(self) -> dict:
        self._ensure_bulk()
        # {código: [(iso3, fecha, valor)]} acumulando entre países.
        buckets: dict[str, list] = {code: [] for _, _, code, _ in _TARGETS}
        # Índice rápido (variable, percentil) → código.
        wanted = {(v, p): code for v, p, code, _ in _TARGETS}
        with zipfile.ZipFile(_CACHE) as zf:
            names = [
                n for n in zf.namelist()
                if n.rsplit("/", 1)[-1].startswith("WID_data_")
                and n.endswith(".csv")
            ]
            for name in names:
                with zf.open(name) as fh:
                    self._parse_country(fh, wanted, buckets)
        ok = 0
        names_by_code = {code: nm for _, _, code, nm in _TARGETS}
        for code, filas in buckets.items():
            n = self._write(code, names_by_code[code], "wealth", filas)
            if n:
                ok += 1
        logger.info("wid: %d/%d indicadores con datos", ok, len(_TARGETS))
        return {"indicadores": len(_TARGETS), "con_datos": ok}

    @staticmethod
    def _parse_country(fh, wanted, buckets) -> None:
        """Filtrar un WID_data_XX.csv y volcar a los buckets."""
        reader = csv.DictReader(
            io.TextIOWrapper(fh, encoding="utf-8"), delimiter=";"
        )
        for row in reader:
            key = (row.get("variable"), row.get("percentile"))
            code = wanted.get(key)
            if code is None:
                continue
            iso3 = _ISO2_TO_3.get(row.get("country", ""))
            if iso3 is None:  # área regional/mundial → descartar
                continue
            raw = row.get("value")
            year = row.get("year")
            if not raw or not year:
                continue
            try:
                buckets[code].append(
                    (iso3, date(int(year), 12, 31), float(raw))
                )
            except (ValueError, TypeError):
                continue

    def _ensure_bulk(self) -> None:
        """Descargar el zip completo si no está en caché."""
        if _CACHE.exists() and _CACHE.stat().st_size > 1_000_000:
            return
        logger.info("wid: descargando bulk (~883 MB)...")
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        self._rate_limit()
        with self._session.get(_BULK_URL, stream=True, timeout=1800) as resp:
            resp.raise_for_status()
            with open(_CACHE, "wb") as out:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    out.write(chunk)
        logger.info("wid: bulk descargado (%d bytes)", _CACHE.stat().st_size)
