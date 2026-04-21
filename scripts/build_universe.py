"""Construir universo de ~5000 empresas cotizadas
desde Wikipedia (listas de índices) y yfinance
screener."""

import logging
import time

import pandas as pd
import requests
import yfinance as yf

from stonks.logger import setup_logger

logger = setup_logger("stonks.universe")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _wiki_tables(url: str) -> list[pd.DataFrame]:
    """Leer tablas de Wikipedia con headers de
    navegador."""
    from io import StringIO
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return pd.read_html(StringIO(resp.text))


# ── Funciones para obtener tickers ──────────────

def get_sp500() -> list[str]:
    """S&P 500 desde Wikipedia."""
    url = (
        "https://en.wikipedia.org/wiki/"
        "List_of_S%26P_500_companies"
    )
    try:
        tables = _wiki_tables(url)
        df = tables[0]
        tickers = df["Symbol"].str.replace(
            ".", "-", regex=False
        ).tolist()
        logger.info("S&P 500: %d tickers", len(tickers))
        return tickers
    except Exception as e:
        logger.warning("Error S&P 500: %s", e)
        return []


def get_sp600() -> list[str]:
    """S&P SmallCap 600 desde Wikipedia."""
    url = (
        "https://en.wikipedia.org/wiki/"
        "List_of_S%26P_600_companies"
    )
    try:
        tables = _wiki_tables(url)
        df = tables[0]
        tickers = df["Symbol"].str.replace(
            ".", "-", regex=False
        ).tolist()
        logger.info("S&P 600: %d tickers", len(tickers))
        return tickers
    except Exception as e:
        logger.warning("Error S&P 600: %s", e)
        return []


def get_sp400() -> list[str]:
    """S&P MidCap 400 desde Wikipedia."""
    url = (
        "https://en.wikipedia.org/wiki/"
        "List_of_S%26P_400_companies"
    )
    try:
        tables = _wiki_tables(url)
        df = tables[0]
        tickers = df["Symbol"].str.replace(
            ".", "-", regex=False
        ).tolist()
        logger.info("S&P 400: %d tickers", len(tickers))
        return tickers
    except Exception as e:
        logger.warning("Error S&P 400: %s", e)
        return []


def get_ftse100() -> list[str]:
    """FTSE 100 desde Wikipedia."""
    url = (
        "https://en.wikipedia.org/wiki/"
        "FTSE_100_Index"
    )
    try:
        tables = _wiki_tables(url)
        for t in tables:
            for col in t.columns:
                cl = str(col).lower()
                if "epic" in cl or "ticker" in cl:
                    tickers = [
                        f"{s}.L" for s in
                        t[col].dropna().tolist()
                        if isinstance(s, str)
                        and len(s) < 10
                    ]
                    if tickers:
                        logger.info(
                            "FTSE 100: %d tickers",
                            len(tickers),
                        )
                        return tickers
            # Intentar por Company column con
            # ticker entre paréntesis
            for col in t.columns:
                cl = str(col).lower()
                if "company" in cl:
                    # Usar la primera columna que
                    # parezca ser ticker (corta)
                    for col2 in t.columns:
                        vals = t[col2].dropna()
                        if vals.empty:
                            continue
                        sample = str(vals.iloc[0])
                        if (1 < len(sample) < 8
                                and sample.isalpha()):
                            tickers = [
                                f"{s}.L"
                                for s in vals.tolist()
                                if isinstance(s, str)
                                and len(s) < 8
                            ]
                            if len(tickers) > 50:
                                logger.info(
                                    "FTSE 100: "
                                    "%d tickers",
                                    len(tickers),
                                )
                                return tickers
        logger.warning("FTSE 100: tabla no encontrada")
        return []
    except Exception as e:
        logger.warning("Error FTSE 100: %s", e)
        return []


def get_ftse250() -> list[str]:
    """FTSE 250 — no hay lista limpia en Wikipedia,
    usar tickers principales hardcoded."""
    # Top ~100 del FTSE 250 por market cap
    tickers = [
        "AUTO.L", "BDEV.L", "BKG.L", "BNZL.L",
        "CBG.L", "CNA.L", "CRDA.L", "DCC.L",
        "DPLM.L", "EMG.L", "FERG.L", "HLMA.L",
        "HWDN.L", "IGG.L", "III.L", "IMB.L",
        "INF.L", "ITRK.L", "JET2.L", "KGF.L",
        "MGNS.L", "MNDI.L", "MONY.L", "NWG.L",
        "PHNX.L", "PSN.L", "RMV.L", "RTO.L",
        "SBRY.L", "SDR.L", "SGE.L", "SGRO.L",
        "SKG.L", "SMIN.L", "SMDS.L", "SPX.L",
        "SSE.L", "SN.L", "TW.L", "WEIR.L",
        "WPP.L", "WTB.L", "BME.L", "DARK.L",
        "DNLM.L", "FOUR.L", "GAW.L", "GNS.L",
        "GRMN.L", "HIK.L", "HYVE.L", "IHG.L",
        "JDW.L", "JMAT.L", "KEL.L", "LAND.L",
        "LMP.L", "MRO.L", "NXT.L", "PAGE.L",
        "PNN.L", "POLY.L", "QQ.L", "RAT.L",
        "RNK.L", "RSW.L", "SAVE.L", "SHED.L",
        "SMWH.L", "SNDR.L", "SXS.L", "TEM.L",
        "UDG.L", "VCT.L", "VSVS.L", "WIX.L",
    ]
    logger.info("FTSE 250: %d tickers", len(tickers))
    return tickers


def get_euro_stoxx600() -> list[str]:
    """Euro Stoxx 600 — principales de Eurozona."""
    # No hay lista completa fácil en Wikipedia,
    # usamos los principales índices nacionales
    indices_wiki = {
        "DAX": (
            "https://en.wikipedia.org/wiki/DAX",
            ".DE",
        ),
        "CAC_40": (
            "https://en.wikipedia.org/wiki/CAC_40",
            ".PA",
        ),
        "IBEX_35": (
            "https://en.wikipedia.org/wiki/IBEX_35",
            ".MC",
        ),
        "AEX": (
            "https://en.wikipedia.org/wiki/AEX_index",
            ".AS",
        ),
        "SMI": (
            "https://en.wikipedia.org/wiki/"
            "Swiss_Market_Index",
            ".SW",
        ),
        "FTSE_MIB": (
            "https://en.wikipedia.org/wiki/FTSE_MIB",
            ".MI",
        ),
        "BEL_20": (
            "https://en.wikipedia.org/wiki/BEL_20",
            ".BR",
        ),
        "OMX_30": (
            "https://en.wikipedia.org/wiki/"
            "OMX_Stockholm_30",
            ".ST",
        ),
        "OBX": (
            "https://en.wikipedia.org/wiki/OBX_Index",
            ".OL",
        ),
        "OMX_C25": (
            "https://en.wikipedia.org/wiki/"
            "OMX_Copenhagen_25",
            ".CO",
        ),
        "OMX_H25": (
            "https://en.wikipedia.org/wiki/"
            "OMX_Helsinki_25",
            ".HE",
        ),
        "PSI_20": (
            "https://en.wikipedia.org/wiki/PSI_20",
            ".LS",
        ),
    }

    all_tickers = []
    for name, (url, suffix) in indices_wiki.items():
        try:
            tables = _wiki_tables(url)
            found = False
            for t in tables:
                for col in t.columns:
                    cl = str(col).lower()
                    if any(k in cl for k in (
                        "ticker", "symbol", "epic",
                        "code",
                    )):
                        raw = t[col].dropna().tolist()
                        tickers = []
                        for s in raw:
                            s = str(s).strip()
                            if not s or len(s) > 15:
                                continue
                            if not s.endswith(suffix):
                                s = f"{s}{suffix}"
                            tickers.append(s)
                        if tickers:
                            all_tickers.extend(tickers)
                            logger.info(
                                "  %s: %d tickers",
                                name, len(tickers),
                            )
                            found = True
                            break
                if found:
                    break
            time.sleep(0.5)
        except Exception as e:
            logger.warning("  Error %s: %s", name, e)

    logger.info(
        "Europa total: %d tickers", len(all_tickers)
    )
    return all_tickers


def get_nikkei225() -> list[str]:
    """Nikkei 225 — principales por market cap."""
    tickers = [
        "7203.T", "6758.T", "6861.T", "6954.T",
        "9984.T", "8306.T", "6501.T", "7741.T",
        "4063.T", "6367.T", "8035.T", "6902.T",
        "4502.T", "4568.T", "6098.T", "7974.T",
        "9432.T", "9433.T", "8001.T", "8058.T",
        "8316.T", "4519.T", "6981.T", "4543.T",
        "7267.T", "6857.T", "6723.T", "3382.T",
        "8766.T", "8411.T", "2802.T", "4661.T",
        "6503.T", "9020.T", "9022.T", "2914.T",
        "4901.T", "5108.T", "6645.T", "7751.T",
        "4578.T", "6762.T", "8031.T", "9021.T",
        "2801.T", "7269.T", "3407.T", "8725.T",
        "6971.T", "4151.T", "6301.T", "7752.T",
        "9531.T", "5401.T", "4507.T", "6326.T",
        "3402.T", "4503.T", "8801.T", "8802.T",
        "5020.T", "2413.T", "6752.T", "4704.T",
        "6504.T", "8053.T", "1925.T", "8830.T",
        "2502.T", "4452.T", "5713.T", "6305.T",
        "4911.T", "8604.T", "6506.T", "1878.T",
        "1928.T", "2503.T", "4755.T", "6701.T",
        "7012.T", "2432.T", "6674.T", "7211.T",
        "7201.T", "5802.T", "5803.T", "4188.T",
        "5019.T", "1605.T", "1801.T", "1802.T",
        "1803.T", "1808.T", "1812.T", "1963.T",
        "2002.T", "2269.T", "2282.T", "2531.T",
        "2768.T", "3086.T", "3099.T", "3101.T",
        "3103.T", "3105.T", "3289.T", "3401.T",
        "3405.T", "3436.T", "3659.T", "3861.T",
        "4004.T", "4005.T", "4021.T", "4042.T",
        "4043.T", "4061.T", "4183.T", "4208.T",
        "4324.T", "4506.T", "4523.T", "4528.T",
        "4631.T", "4689.T", "4902.T", "4967.T",
        "5002.T", "5101.T", "5201.T", "5214.T",
        "5232.T", "5233.T", "5301.T", "5332.T",
        "5333.T", "5406.T", "5411.T", "5541.T",
        "5631.T", "5706.T", "5707.T", "5711.T",
        "5714.T", "5801.T", "5901.T", "6098.T",
        "6103.T", "6113.T", "6178.T", "6361.T",
        "6370.T", "6471.T", "6472.T", "6473.T",
        "6479.T", "6501.T", "6503.T", "6504.T",
        "6506.T", "6588.T", "6594.T", "6645.T",
        "6702.T", "6724.T", "6753.T", "6770.T",
        "6841.T", "6856.T", "6952.T", "6976.T",
        "6988.T", "7004.T", "7011.T", "7013.T",
        "7186.T", "7202.T", "7205.T", "7261.T",
        "7270.T", "7272.T", "7731.T", "7733.T",
        "7735.T", "7762.T", "7832.T", "7911.T",
        "7912.T", "7951.T", "8002.T", "8015.T",
        "8028.T", "8233.T", "8252.T", "8253.T",
        "8267.T", "8303.T", "8304.T", "8308.T",
        "8309.T", "8331.T", "8354.T", "8355.T",
        "8591.T", "8601.T", "8628.T", "8630.T",
        "8697.T", "8750.T", "8795.T", "9001.T",
        "9005.T", "9007.T", "9008.T", "9009.T",
        "9064.T", "9101.T", "9104.T", "9107.T",
        "9202.T", "9301.T", "9501.T", "9502.T",
        "9503.T", "9532.T", "9602.T", "9613.T",
        "9735.T", "9766.T", "9983.T",
    ]
    # Deduplicar
    tickers = list(dict.fromkeys(tickers))
    logger.info("Nikkei 225: %d tickers", len(tickers))
    return tickers


def get_hsi() -> list[str]:
    """Hang Seng — principales HK/China."""
    tickers = [
        "0700.HK", "9988.HK", "0941.HK", "1299.HK",
        "3690.HK", "2318.HK", "0005.HK", "9618.HK",
        "9888.HK", "1810.HK", "2020.HK", "0003.HK",
        "0016.HK", "0388.HK", "2269.HK", "0001.HK",
        "0011.HK", "0027.HK", "0066.HK", "0175.HK",
        "0241.HK", "0267.HK", "0288.HK", "0386.HK",
        "0669.HK", "0688.HK", "0762.HK", "0823.HK",
        "0857.HK", "0868.HK", "0883.HK", "0939.HK",
        "0960.HK", "0968.HK", "1038.HK", "1044.HK",
        "1093.HK", "1109.HK", "1113.HK", "1177.HK",
        "1211.HK", "1398.HK", "1876.HK", "1928.HK",
        "1997.HK", "2007.HK", "2018.HK", "2196.HK",
        "2313.HK", "2319.HK", "2331.HK", "2382.HK",
        "2388.HK", "2628.HK", "2688.HK", "3328.HK",
        "3968.HK", "3988.HK", "6098.HK", "6618.HK",
        "6862.HK", "9633.HK", "9698.HK", "9868.HK",
        "9901.HK", "9961.HK", "9999.HK",
    ]
    logger.info("HSI: %d tickers", len(tickers))
    return tickers


def get_additional_asia() -> list[str]:
    """Tickers adicionales de Asia (India, Korea,
    Australia, Singapur, Taiwán)."""
    # Listas hardcoded de principales por mercado
    # ya que Wikipedia no tiene formato consistente
    india = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS",
        "INFY.NS", "ICICIBANK.NS", "HINDUNILVR.NS",
        "BHARTIARTL.NS", "ITC.NS", "SBIN.NS",
        "LT.NS", "BAJFINANCE.NS", "KOTAKBANK.NS",
        "ASIANPAINT.NS", "MARUTI.NS",
        "TATAMOTORS.NS", "WIPRO.NS", "HCLTECH.NS",
        "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
        "AXISBANK.NS", "NESTLEIND.NS", "ADANIGREEN.NS",
        "BAJAJFINSV.NS", "TECHM.NS", "NTPC.NS",
        "POWERGRID.NS", "M&M.NS", "TATASTEEL.NS",
        "JSWSTEEL.NS", "ONGC.NS", "ADANIENT.NS",
        "GRASIM.NS", "DIVISLAB.NS", "COALINDIA.NS",
        "HINDALCO.NS", "DRREDDY.NS", "CIPLA.NS",
        "EICHERMOT.NS", "BPCL.NS", "HEROMOTOCO.NS",
        "BRITANNIA.NS", "APOLLOHOSP.NS",
        "TATACONSUM.NS", "PIDILITIND.NS",
        "INDUSINDBK.NS", "DABUR.NS", "GODREJCP.NS",
        "HAVELLS.NS", "SBILIFE.NS",
    ]

    korea = [
        "005930.KS", "000660.KS", "373220.KS",
        "207940.KS", "005380.KS", "035420.KS",
        "068270.KS", "051910.KS", "006400.KS",
        "035720.KS", "003550.KS", "105560.KS",
        "055550.KS", "034730.KS", "000270.KS",
        "012330.KS", "028260.KS", "066570.KS",
        "032830.KS", "096770.KS", "018260.KS",
        "033780.KS", "003670.KS", "009150.KS",
        "086790.KS",
    ]

    australia = [
        "BHP.AX", "CBA.AX", "CSL.AX", "NAB.AX",
        "WBC.AX", "ANZ.AX", "WES.AX", "MQG.AX",
        "FMG.AX", "RIO.AX", "WOW.AX", "TLS.AX",
        "WDS.AX", "ALL.AX", "COL.AX", "STO.AX",
        "TCL.AX", "GMG.AX", "REA.AX", "QBE.AX",
        "MIN.AX", "SHL.AX", "NCM.AX", "ORG.AX",
        "AMC.AX", "TWE.AX", "CPU.AX", "IAG.AX",
        "SUN.AX", "JHX.AX",
    ]

    taiwan = [
        "2330.TW", "2317.TW", "2454.TW",
        "2412.TW", "2308.TW", "2881.TW",
        "2882.TW", "2303.TW", "1301.TW",
        "1303.TW", "2886.TW", "3711.TW",
        "2891.TW", "2884.TW", "2357.TW",
        "3008.TW", "2382.TW", "2002.TW",
        "1326.TW", "5880.TW", "2892.TW",
        "3034.TW", "2207.TW", "4904.TW",
        "2912.TW",
    ]

    singapore = [
        "D05.SI", "O39.SI", "U11.SI", "Z74.SI",
        "BN4.SI", "C38U.SI", "A17U.SI", "Y92.SI",
        "S58.SI", "C09.SI", "G13.SI", "S63.SI",
        "V03.SI", "U96.SI", "BS6.SI",
    ]

    all_t = india + korea + australia + taiwan + (
        singapore
    )
    logger.info(
        "Asia adicional: %d tickers", len(all_t)
    )
    return all_t


def get_latam() -> list[str]:
    """Principales empresas de Latinoamérica."""
    brazil = [
        "VALE3.SA", "PETR4.SA", "ITUB4.SA",
        "BBDC4.SA", "WEGE3.SA", "ABEV3.SA",
        "RENT3.SA", "B3SA3.SA", "GGBR4.SA",
        "SUZB3.SA", "PETR3.SA", "BBAS3.SA",
        "JBSS3.SA", "RAIL3.SA", "LREN3.SA",
        "HAPV3.SA", "RDOR3.SA", "BPAC11.SA",
        "VIVT3.SA", "SBSP3.SA", "CMIG4.SA",
        "CSAN3.SA", "RADL3.SA", "CCRO3.SA",
        "KLBN11.SA", "TOTS3.SA", "ENEV3.SA",
        "PRIO3.SA", "MGLU3.SA", "ELET3.SA",
        "BRFS3.SA", "EMBR3.SA", "HYPE3.SA",
        "ASAI3.SA", "NTCO3.SA", "MULT3.SA",
        "EQTL3.SA", "TAEE11.SA", "FLRY3.SA",
        "VBBR3.SA",
    ]

    mexico = [
        "WALMEX.MX", "FEMSAUBD.MX", "GFNORTEO.MX",
        "AMXB.MX", "CEMEXCPO.MX", "GMEXICOB.MX",
        "AC.MX", "BIMBOA.MX", "TLEVISACPO.MX",
        "GAPB.MX", "ASURB.MX", "GRUMAB.MX",
        "KIMBERA.MX", "LIVEPOLC-1.MX",
        "PE&OLES.MX", "ALSEA.MX", "GCARSOA1.MX",
        "OMAB.MX", "PINFRA.MX", "VOLARA.MX",
    ]

    chile_col_arg = [
        "SQM", "BSANTANDER.SN", "COPEC.SN",
        "FALABELLA.SN", "CENCOSUD.SN",
        "ECOPETROL.BVC", "PFBCOLOM.BVC",
        "ISA.BVC", "NUTRESA.BVC",
        "YPF", "GGAL", "BMA", "PAM", "CEPU",
    ]

    all_t = brazil + mexico + chile_col_arg
    logger.info("Latam: %d tickers", len(all_t))
    return all_t


def get_mena_africa() -> list[str]:
    """Principales de Medio Oriente y África."""
    saudi = [
        "2222.SR", "1180.SR", "2010.SR", "7010.SR",
        "1120.SR", "2350.SR", "1150.SR", "2380.SR",
        "4013.SR", "2001.SR",
    ]

    uae = [
        "FAB.AE", "ETISALAT.AE", "ADNOCDIST.AE",
        "EMIRATES.AE", "DIB.AE",
    ]

    south_africa = [
        "NPN.JO", "BTI.JO", "SOL.JO", "SBK.JO",
        "FSR.JO", "AGL.JO", "BIL.JO", "SHP.JO",
        "AMS.JO", "MTN.JO", "VOD.JO", "REM.JO",
        "DSY.JO", "NED.JO", "ABG.JO",
    ]

    israel = [
        "CHKP", "NICE", "MNDY", "CYBR", "WIX",
        "TEVA", "INMD", "FVRR", "GLOB", "LSPD",
    ]

    turkey = [
        "THYAO.IS", "GARAN.IS", "ASELS.IS",
        "BIMAS.IS", "EREGL.IS", "KCHOL.IS",
        "SAHOL.IS", "TUPRS.IS", "AKBNK.IS",
        "SISE.IS",
    ]

    all_t = (
        saudi + uae + south_africa + israel + turkey
    )
    logger.info("MENA/África: %d tickers", len(all_t))
    return all_t


def build_universe() -> list[str]:
    """Construir universo completo de ~5000 tickers."""
    logger.info("=== Construyendo universo ===")

    all_tickers = []

    # US: S&P 500 + 400 + 600 = ~1500
    logger.info("--- US ---")
    all_tickers.extend(get_sp500())
    time.sleep(1)
    all_tickers.extend(get_sp400())
    time.sleep(1)
    all_tickers.extend(get_sp600())
    time.sleep(1)

    # UK: FTSE 100 + 250 = ~350
    logger.info("--- UK ---")
    all_tickers.extend(get_ftse100())
    time.sleep(1)
    all_tickers.extend(get_ftse250())
    time.sleep(1)

    # Europa continental: ~400
    logger.info("--- Europa continental ---")
    all_tickers.extend(get_euro_stoxx600())
    time.sleep(1)

    # Japón: Nikkei 225
    logger.info("--- Japón ---")
    all_tickers.extend(get_nikkei225())
    time.sleep(1)

    # Hong Kong / China
    logger.info("--- Hong Kong ---")
    all_tickers.extend(get_hsi())
    time.sleep(1)

    # Asia adicional: India, Korea, Australia,
    # Taiwan, Singapur ~145
    logger.info("--- Asia adicional ---")
    all_tickers.extend(get_additional_asia())

    # Latam ~74
    logger.info("--- Latam ---")
    all_tickers.extend(get_latam())

    # MENA/Africa ~50
    logger.info("--- MENA/Africa ---")
    all_tickers.extend(get_mena_africa())

    # Deduplicar
    seen = set()
    unique = []
    for t in all_tickers:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            unique.append(t)

    logger.info(
        "=== Universo total: %d tickers únicos ===",
        len(unique),
    )
    return unique


if __name__ == "__main__":
    tickers = build_universe()
    # Guardar a archivo
    out = (
        "/home/marc/Projects/db-projects/stonks/"
        "data/universe_tickers.txt"
    )
    with open(out, "w") as f:
        for t in tickers:
            f.write(t + "\n")
    print(f"Guardados {len(tickers)} tickers en {out}")
