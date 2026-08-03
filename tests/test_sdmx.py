"""Tests de los parsers macro (lógica pura, sin red ni BD).

Cubre: decodificación de periodos, aplanado SDMX-JSON (con y sin
conversión ISO-2→ISO-3), JSON-stat de Eurostat (índice mixto-radix),
parseo de WHO GHO y de los CSV por país de WID, y el mapeo M49 de
Comtrade.
"""

from datetime import date

from stonks.fetchers.sdmx import (
    BISFetcher,
    OECDFetcher,
    _period_to_date,
)


def test_period_to_date():
    assert _period_to_date("2026") == date(2026, 12, 31)
    assert _period_to_date("2026-04") == date(2026, 4, 28)
    assert _period_to_date("2026-Q2") == date(2026, 6, 28)
    assert _period_to_date("basura") is None


# Fixture SDMX-JSON mínimo: 2 países × 2 periodos, forma 'structure'.
_SDMX = {
    "data": {
        "structure": {
            "dimensions": {
                "observation": [
                    {
                        "id": "REF_AREA",
                        "values": [{"id": "ES"}, {"id": "US"}],
                    },
                    {
                        "id": "TIME_PERIOD",
                        "values": [{"id": "2023-01"}, {"id": "2023-02"}],
                    },
                ]
            }
        },
        "dataSets": [{"observations": {"0:0": [1.5], "1:1": [2.5]}}],
    }
}


def test_flatten_convierte_iso2():
    # BIS usa ISO-2 → debe convertir ES→ESP, US→USA.
    filas = BISFetcher()._flatten(_SDMX)
    por_pais = {f[0]: f for f in filas}
    assert por_pais["ESP"][1] == date(2023, 1, 28)
    assert por_pais["ESP"][2] == 1.5
    assert por_pais["USA"][1] == date(2023, 2, 28)
    assert por_pais["USA"][2] == 2.5


def test_flatten_sin_iso2_usa_codigo_tal_cual():
    # OECD no convierte: el código de país se usa literal.
    payload = {
        "data": {
            "structures": [
                {
                    "dimensions": {
                        "observation": [
                            {"id": "REF_AREA", "values": [{"id": "ESP"}]},
                            {
                                "id": "TIME_PERIOD",
                                "values": [{"id": "2023-03"}],
                            },
                        ]
                    }
                }
            ],
            "dataSets": [{"observations": {"0:0": [3.5]}}],
        }
    }
    filas = OECDFetcher()._flatten(payload)
    assert filas == [("ESP", date(2023, 3, 28), 3.5)]


def test_flatten_vacio():
    assert OECDFetcher()._flatten({}) == []


def test_eurostat_jsonstat():
    from stonks.fetchers.eurostat import EurostatFetcher

    # 2 geos (ES, DE) × 2 tiempos; valores por índice lineal row-major.
    d = {
        "id": ["geo", "time"],
        "size": [2, 2],
        "dimension": {
            "geo": {"category": {"index": {"ES": 0, "DE": 1}}},
            "time": {"category": {"index": {"2023-01": 0, "2023-02": 1}}},
        },
        "value": {"0": 1.0, "3": 4.0},
    }
    filas = EurostatFetcher._flatten_jsonstat(d)
    por_pais = {f[0]: f for f in filas}
    # índice 0 = (ES, 2023-01); índice 3 = (DE, 2023-02)
    assert por_pais["ESP"] == ("ESP", date(2023, 1, 28), 1.0)
    assert por_pais["DEU"] == ("DEU", date(2023, 2, 28), 4.0)


def test_who_parse_filtra_pais_y_sexo():
    from stonks.fetchers.who import WHOFetcher

    records = [
        {
            "SpatialDimType": "COUNTRY",
            "SpatialDim": "ESP",
            "TimeDim": 2020,
            "NumericValue": 83.0,
            "Dim1": "SEX_BTSX",
        },
        {
            "SpatialDimType": "REGION",
            "SpatialDim": "EUR",
            "TimeDim": 2020,
            "NumericValue": 80.0,
            "Dim1": "SEX_BTSX",
        },
        {
            "SpatialDimType": "COUNTRY",
            "SpatialDim": "ESP",
            "TimeDim": 2020,
            "NumericValue": 99.0,
            "Dim1": "SEX_MLE",
        },
    ]
    # dim1=None → solo el total (descarta región y desglose por sexo).
    filas = WHOFetcher._parse(records, dim1=None)
    assert filas == [("ESP", date(2020, 12, 31), 83.0)]


def test_wid_parse_country():
    import io

    from stonks.fetchers.wid import WIDFetcher

    wanted = {("sptincj992", "p99p100"): "WID_INC_TOP1"}
    buckets = {"WID_INC_TOP1": []}
    contenido = (
        "country;variable;percentile;year;value\n"
        "ES;sptincj992;p99p100;2021;0.1227\n"
        "QE;sptincj992;p99p100;2021;0.5\n"
    )
    fh = io.BytesIO(contenido.encode("utf-8"))
    WIDFetcher._parse_country(fh, wanted, buckets)
    # ES es país (→ESP); QE es agregado regional (sin ISO-3) → descartado.
    assert buckets["WID_INC_TOP1"] == [("ESP", date(2021, 12, 31), 0.1227)]


def test_comtrade_m49():
    from stonks.fetchers.comtrade import _M49_TO_3

    assert _M49_TO_3[724] == "ESP"
    assert _M49_TO_3[840] == "USA"
