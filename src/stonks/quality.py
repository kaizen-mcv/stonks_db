"""Checks de calidad de datos → meta.data_quality.

Registra, por dominio de la economía mundial, la cobertura de países y la
frescura (año más reciente) del panel gold. Es informativo y se ejecuta
al final de build_gold. Idempotente: borra sus filas previas y reinserta.
"""

from datetime import datetime

from sqlalchemy import text

from stonks.db import engine
from stonks.logger import get_logger

logger = get_logger("stonks.quality")

# (dominio, entidad, consulta de conteo de países, consulta de año máx.)
_CHECKS = [
    (
        "world_panel",
        "gold.mart_country_year",
        "SELECT count(DISTINCT country_code) FROM gold.mart_country_year",
        "SELECT max(year) FROM gold.mart_country_year",
    ),
    (
        "trade",
        "trade.flow",
        "SELECT count(DISTINCT reporter_code) FROM trade.flow",
        "SELECT max(period) FROM trade.flow",
    ),
    (
        "energy",
        "energy.balance",
        "SELECT count(DISTINCT country_code) FROM energy.balance",
        "SELECT max(period) FROM energy.balance",
    ),
    (
        "macro",
        "macro.series",
        "SELECT count(DISTINCT country_code) FROM macro.series",
        "SELECT extract(year FROM max(date)) FROM macro.data_point",
    ),
]


def check_world_quality() -> dict:
    """Calcular cobertura/frescura por dominio y guardar en meta."""
    resumen: dict[str, dict] = {}
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM meta.data_quality WHERE domain IN "
                "('world_panel','trade','energy','macro')"
            )
        )
        for domain, entidad, q_paises, q_anio in _CHECKS:
            paises = conn.execute(text(q_paises)).scalar() or 0
            anio = conn.execute(text(q_anio)).scalar()
            # Completitud = países cubiertos sobre ~200 economías.
            score = round(min(paises / 200.0, 1.0) * 100, 1)
            fresh = None
            if anio:
                # 0 si la última fecha es futura (IMF proyecta a años+).
                fresh = max(0, datetime.now().year - int(anio))
            conn.execute(
                text(
                    "INSERT INTO meta.data_quality "
                    "(domain, entity_type, entity_id, completeness_score, "
                    " freshness_days, last_assessed) VALUES "
                    "(:d, 'panel', :e, :s, :f, now())"
                ),
                {"d": domain, "e": entidad, "s": score, "f": fresh},
            )
            resumen[domain] = {"paises": paises, "anio": anio}
    logger.info("Calidad economía mundial: %s", resumen)
    return resumen
