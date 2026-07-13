"""Tests del parser SDMX de comercio WITS (lógica pura)."""

from stonks.transform.trade import TradeTransform

# Fixture SDMX-JSON mínimo: España → Francia y Alemania, exportaciones 2022.
_PAYLOAD = {
    "structure": {
        "dimensions": {
            "series": [
                {"id": "FREQ", "values": [{"id": "A"}]},
                {"id": "REPORTER", "values": [{"id": "ESP"}]},
                {"id": "PARTNER", "values": [{"id": "FRA"}, {"id": "DEU"}]},
                {"id": "PRODUCTCODE", "values": [{"id": "Total"}]},
                {"id": "INDICATOR", "values": [{"id": "XPRT-TRD-VL"}]},
            ],
            "observation": [{"id": "TIME", "values": [{"id": "2022"}]}],
        }
    },
    "dataSets": [
        {
            "series": {
                "0:0:0:0:0": {"observations": {"0": [63100.0]}},
                "0:0:1:0:0": {"observations": {"0": [39400.0]}},
            }
        }
    ],
}


def test_parse_decodifica_flujos():
    valid = {"ESP", "FRA", "DEU"}
    filas = TradeTransform._parse(_PAYLOAD, valid, src_id=1)
    assert len(filas) == 2
    por_socio = {f["partner_code"]: f for f in filas}
    assert por_socio["FRA"]["value_usd_k"] == 63100.0
    assert por_socio["FRA"]["flow"] == "X"
    assert por_socio["FRA"]["period"] == 2022
    assert por_socio["DEU"]["value_usd_k"] == 39400.0


def test_parse_omite_reporter_invalido():
    # Si el reporter no está en ref.country, no se emite nada.
    filas = TradeTransform._parse(_PAYLOAD, {"FRA", "DEU"}, src_id=1)
    assert filas == []


def test_parse_payload_vacio():
    assert TradeTransform._parse({}, {"ESP"}, src_id=1) == []
