"""Conversion de importes a dolares.

Yahoo devuelve los importes en la moneda de cotizacion del valor
—capitalizacion, valor de una participacion, importe de una operacion
de un insider— y el proyecto los guarda en columnas que se llaman
`_usd`. Cuando no se convierte, la columna miente sobre su unidad:
Toyota figuraba con 34,5 billones (yenes) y una posicion de Vanguard en
Samsung con 18 billones (wones).

Vive aparte porque el mismo defecto aparecio en tres fetchers
distintos y conviene que la correccion sea una sola.
"""

from sqlalchemy import text

from stonks.logger import get_logger

logger = get_logger("stonks.divisas")

# Un tipo de cambio de hace anos convertiria mal y en silencio.
MAX_ANTIGUEDAD_TIPO = 30

# Monedas que Yahoo cotiza en subunidad, con su moneda real.
SUBUNIDADES = {
    "GBp": ("GBP", 100),
    "ZAc": ("ZAR", 100),
    "ILA": ("ILS", 100),
}


def normalizar_moneda(codigo: str | None) -> tuple[str | None, int]:
    """Devolver (moneda real, divisor) para una moneda de Yahoo."""
    if not codigo:
        return None, 1
    real, factor = SUBUNIDADES.get(codigo, (codigo, 1))
    return real, factor


def tipo_de_cambio(session, moneda: str) -> float | None:
    """Ultimo USD/moneda disponible, o None si no hay uno reciente.

    El par puede estar guardado en cualquiera de los dos sentidos:
    USDJPY existe, pero el euro y el dolar australiano se cotizan al
    reves (EURUSD, AUDUSD). Se admite el invertido y se toma su
    reciproco.
    """
    tipo = session.execute(
        text(
            "SELECT r.close FROM forex.rate_daily r "
            "JOIN forex.currency_pair p ON p.id = r.pair_id "
            "WHERE p.base_currency = 'USD' AND p.quote_currency = :m "
            "AND r.date > CURRENT_DATE - :dias "
            "ORDER BY r.date DESC LIMIT 1"
        ),
        {"m": moneda, "dias": MAX_ANTIGUEDAD_TIPO},
    ).scalar()

    if not tipo:
        inverso = session.execute(
            text(
                "SELECT r.close FROM forex.rate_daily r "
                "JOIN forex.currency_pair p ON p.id = r.pair_id "
                "WHERE p.base_currency = :m "
                "AND p.quote_currency = 'USD' "
                "AND r.date > CURRENT_DATE - :dias "
                "ORDER BY r.date DESC LIMIT 1"
            ),
            {"m": moneda, "dias": MAX_ANTIGUEDAD_TIPO},
        ).scalar()
        if inverso and float(inverso) > 0:
            tipo = 1.0 / float(inverso)

    return float(tipo) if tipo and float(tipo) > 0 else None


def a_usd(session, importe, moneda: str | None):
    """Convertir un importe a dolares con el tipo de cambio vigente.

    Si no hay tipo de cambio reciente para esa moneda se devuelve None
    en lugar del importe sin convertir: es preferible no tener dato a
    tener uno que miente sobre su unidad.
    """
    if importe is None:
        return None

    moneda, _ = normalizar_moneda(moneda)
    importe = float(importe)

    if not moneda or moneda == "USD":
        return importe

    tipo = tipo_de_cambio(session, moneda)
    if tipo is None:
        logger.warning(
            "Sin tipo de cambio USD/%s de los ultimos %d dias: "
            "importe sin convertir, se descarta",
            moneda,
            MAX_ANTIGUEDAD_TIPO,
        )
        return None
    return importe / tipo
