"""Tests de los fetchers incorporados en la auditoría 2026-08.

Cubre la lógica pura de parseo y normalización: nada de red ni de BD.
Los casos elegidos son los que rompieron durante la integración, para
que una regresión vuelva a saltar aquí en lugar de en producción.
"""

from datetime import date

import pytest

from stonks.fetchers.cftc_cot import CftcCotFetcher
from stonks.fetchers.damodaran import DamodaranFetcher
from stonks.fetchers.fama_french import FamaFrenchFetcher
from stonks.fetchers.gleif import GleifFetcher


# ── CFTC: informe COT ────────────────────────────


def test_cot_fecha_iso_con_hora():
    """Socrata devuelve la fecha con hora: '2022-09-13T00:00:00.000'."""
    assert CftcCotFetcher._fecha(
        "2022-09-13T00:00:00.000"
    ) == date(2022, 9, 13)
    assert CftcCotFetcher._fecha(None) is None
    assert CftcCotFetcher._fecha("no es fecha") is None


def test_cot_entero_tolera_decimales_y_vacios():
    assert CftcCotFetcher._entero("119219") == 119219
    assert CftcCotFetcher._entero("119219.0") == 119219
    assert CftcCotFetcher._entero("") is None
    assert CftcCotFetcher._entero(None) is None
    assert CftcCotFetcher._entero("N/A") is None


def test_cot_texto_trunca_y_limpia():
    assert CftcCotFetcher._texto("  CBT  ", 20) == "CBT"
    assert CftcCotFetcher._texto("A" * 300, 200) == "A" * 200
    assert CftcCotFetcher._texto("   ", 20) is None
    assert CftcCotFetcher._texto(None, 20) is None


def test_cot_deduplica_por_contrato_y_fecha():
    """ON CONFLICT no resuelve duplicados dentro del mismo INSERT.

    La paginación de Socrata llegó a devolver filas repetidas y el
    upsert reventaba; deduplicar antes es lo que lo arregla.
    """
    informes = [
        {"contract_code": "001602", "report_date": date(2022, 9, 13),
         "open_interest": 100},
        {"contract_code": "001602", "report_date": date(2022, 9, 13),
         "open_interest": 200},
        {"contract_code": "001602", "report_date": date(2022, 9, 20),
         "open_interest": 300},
    ]
    salida = CftcCotFetcher._deduplicar(informes)
    assert len(salida) == 2
    # Gana la última aparición.
    por_fecha = {f["report_date"]: f["open_interest"] for f in salida}
    assert por_fecha[date(2022, 9, 13)] == 200


# ── Fama-French: parseo de los CSV ───────────────


_CSV_FF = """This file was created using the 202606 CRSP database.
The 1-month TBill rate data are from Ibbotson Associates.

,Mkt-RF,SMB,HML,RMW,CMA,RF
196307,   -0.39,   -0.48,   -0.81,    0.64,   -1.15,    0.27
196308,    5.08,   -0.80,    1.70,    0.40,   -0.38,    0.25

 Annual Factors: January-December
1964,    2.20,   -0.50,    1.10,    0.30,    0.90,    3.54
"""


def test_fama_french_extrae_solo_la_seccion_mensual():
    filas = FamaFrenchFetcher._parsear(_CSV_FF)
    fechas = {f for f, _, _ in filas}
    assert fechas == {date(1963, 7, 1), date(1963, 8, 1)}
    # 2 meses × 6 factores.
    assert len(filas) == 12


def test_fama_french_mapea_nombres_de_factor():
    filas = FamaFrenchFetcher._parsear(_CSV_FF)
    factores = {f for _, f, _ in filas}
    assert factores == {"mkt_rf", "smb", "hml", "rmw", "cma", "rf"}


def test_fama_french_descarta_el_centinela_de_ausente():
    """La fuente marca los datos que faltan con -99.99."""
    csv = (
        "nota\n"
        "\n"
        ",Mkt-RF,SMB,HML,RMW,CMA,RF\n"
        "198907    ,0.60   ,-0.39   ,15.53  ,-99.99  ,-99.99    ,0.70\n"
    )
    filas = FamaFrenchFetcher._parsear(csv)
    factores = {f for _, f, _ in filas}
    assert "rmw" not in factores
    assert "cma" not in factores
    assert factores == {"mkt_rf", "smb", "hml", "rf"}


def test_fama_french_csv_sin_cabecera_no_revienta():
    assert FamaFrenchFetcher._parsear("solo texto\nsin datos\n") == []


# ── Damodaran: normalización de países ───────────


def test_damodaran_normaliza_acentos_y_puntuacion():
    assert DamodaranFetcher._normalizar("Côte d'Ivoire") == "cote d ivoire"
    assert DamodaranFetcher._normalizar("Korea, Republic of") == (
        "korea republic of"
    )
    assert DamodaranFetcher._normalizar("  ESPAÑA  ") == "espana"


def test_damodaran_convierte_a_porcentaje():
    """La fuente publica tantos por uno; la BD guarda porcentajes."""
    assert DamodaranFetcher._numero(0.0486906451636496) == 4.8691
    assert DamodaranFetcher._numero(0) == 0.0
    assert DamodaranFetcher._numero(None) is None
    assert DamodaranFetcher._numero("texto") is None


def test_damodaran_deduplica_paises_que_colapsan_al_mismo_iso():
    """Abu Dhabi, Dubai y Sharjah son todos ARE en ISO 3166."""
    lote = [
        {"country_code": "ARE", "year": 2026, "corporate_tax_rate": 9.0},
        {"country_code": "ARE", "year": 2026, "corporate_tax_rate": 9.0},
        {"country_code": "ESP", "year": 2026, "corporate_tax_rate": 25.0},
    ]
    salida = DamodaranFetcher._deduplicar(lote, ("country_code", "year"))
    assert len(salida) == 2
    assert {f["country_code"] for f in salida} == {"ARE", "ESP"}


# ── GLEIF: normalización de nombres legales ──────


@pytest.mark.parametrize(
    "nombre,esperado",
    [
        ("Apple Inc.", "apple"),
        ("NVIDIA Corporation", "nvidia"),
        ("Samsung Electronics Co., Ltd.", "samsung electronics"),
        ("SAMSUNG ELECTRONICS COMPANY LIMITED", "samsung electronics"),
        ("Roche Holding AG", "roche"),
        ("ASML Holding N.V.", "asml"),
    ],
)
def test_gleif_normaliza_sufijos_societarios(nombre, esperado):
    assert GleifFetcher._normalizar(nombre) == esperado


def test_gleif_matriz_y_filial_normalizan_igual():
    """Este es justo el riesgo que obliga a filtrar por país.

    'SAMSUNG ELECTRONICS GMBH' (filial alemana) y la matriz coreana
    colapsan al mismo texto y puntúan 1.0, así que la similitud de
    nombre por sí sola no basta para elegir.
    """
    matriz = GleifFetcher._normalizar("Samsung Electronics Co., Ltd.")
    filial = GleifFetcher._normalizar("SAMSUNG ELECTRONICS GMBH")
    assert matriz == filial


def test_gleif_parsea_registro_de_la_api():
    item = {
        "id": "HWUPKR0MPOU8FGXBT394",
        "attributes": {
            "lei": "HWUPKR0MPOU8FGXBT394",
            "entity": {
                "legalName": {"name": "Apple Inc."},
                "legalAddress": {"country": "US", "city": "Glendale"},
                "jurisdiction": "US-CA",
                "status": "ACTIVE",
                "category": "GENERAL",
                "associatedEntity": {"lei": None},
            },
            "registration": {"status": "ISSUED"},
        },
    }
    reg = GleifFetcher._parsear(item)
    assert reg["lei"] == "HWUPKR0MPOU8FGXBT394"
    assert reg["legal_name"] == "Apple Inc."
    assert reg["country_alpha2"] == "US"
    assert reg["entity_status"] == "ACTIVE"
    assert reg["city"] == "Glendale"


def test_gleif_registro_incompleto_devuelve_none():
    assert GleifFetcher._parsear({"attributes": {}}) is None
    assert GleifFetcher._parsear({}) is None


# ── UNCTAD: periodos anuales y trimestrales ──────


def test_unctad_periodo_anual():
    from stonks.fetchers.unctad import UNCTADFetcher

    assert UNCTADFetcher._periodo_a_fecha("2024") == date(2024, 12, 31)
    assert UNCTADFetcher._periodo_a_fecha("2024.0") == date(2024, 12, 31)


def test_unctad_periodo_trimestral():
    """LSCI es trimestral ("2006Q01") y se descartaba entera."""
    from stonks.fetchers.unctad import UNCTADFetcher

    assert UNCTADFetcher._periodo_a_fecha("2006Q01") == date(2006, 3, 31)
    assert UNCTADFetcher._periodo_a_fecha("2006Q02") == date(2006, 6, 30)
    assert UNCTADFetcher._periodo_a_fecha("2006Q03") == date(2006, 9, 30)
    assert UNCTADFetcher._periodo_a_fecha("2006Q04") == date(2006, 12, 31)


def test_unctad_periodo_invalido():
    from stonks.fetchers.unctad import UNCTADFetcher

    assert UNCTADFetcher._periodo_a_fecha("") is None
    assert UNCTADFetcher._periodo_a_fecha("nan") is None
    assert UNCTADFetcher._periodo_a_fecha("2006Q09") is None
    assert UNCTADFetcher._periodo_a_fecha("basura") is None
    # Fuera del rango plausible.
    assert UNCTADFetcher._periodo_a_fecha("1500") is None


def test_unctad_descomprimir_pasa_csv_plano():
    """Si UNCTAD vuelve al CSV sin comprimir, no debe romperse."""
    from stonks.fetchers.unctad import UNCTADFetcher

    plano = b"Year,Economy Label,Value\n2024,Spain,1.0\n"
    assert UNCTADFetcher._descomprimir(plano) == plano
