"""Fetcher de ETFs y fondos via yfinance."""

import csv
from pathlib import Path

import yfinance as yf
from sqlalchemy import and_

import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.fund import Fund, NavDaily
from stonks.models.meta import DataSource

# ETFs principales globales
ETFS = [
    # US Broad Market
    (
        "SPY",
        "SPDR S&P 500 ETF",
        "etf",
        "equity",
        "US",
        "index",
        "State Street",
    ),
    ("QQQ", "Invesco QQQ Trust", "etf", "equity", "US", "index", "Invesco"),
    (
        "VTI",
        "Vanguard Total Stock Market",
        "etf",
        "equity",
        "US",
        "index",
        "Vanguard",
    ),
    ("IWM", "iShares Russell 2000", "etf", "equity", "US", "index", "iShares"),
    ("VOO", "Vanguard S&P 500", "etf", "equity", "US", "index", "Vanguard"),
    # International
    (
        "EFA",
        "iShares MSCI EAFE",
        "etf",
        "equity",
        "Developed ex-US",
        "index",
        "iShares",
    ),
    (
        "VWO",
        "Vanguard FTSE Emerging Markets",
        "etf",
        "equity",
        "Emerging Markets",
        "index",
        "Vanguard",
    ),
    (
        "EEM",
        "iShares MSCI Emerging Markets",
        "etf",
        "equity",
        "Emerging Markets",
        "index",
        "iShares",
    ),
    (
        "VEA",
        "Vanguard FTSE Developed Markets",
        "etf",
        "equity",
        "Developed ex-US",
        "index",
        "Vanguard",
    ),
    # Fixed Income
    (
        "AGG",
        "iShares Core US Aggregate Bond",
        "etf",
        "fixed_income",
        "US",
        "index",
        "iShares",
    ),
    (
        "TLT",
        "iShares 20+ Year Treasury Bond",
        "etf",
        "fixed_income",
        "US",
        "index",
        "iShares",
    ),
    (
        "HYG",
        "iShares iBoxx High Yield Corp",
        "etf",
        "fixed_income",
        "US",
        "index",
        "iShares",
    ),
    (
        "LQD",
        "iShares iBoxx IG Corporate Bond",
        "etf",
        "fixed_income",
        "US",
        "index",
        "iShares",
    ),
    (
        "BND",
        "Vanguard Total Bond Market",
        "etf",
        "fixed_income",
        "US",
        "index",
        "Vanguard",
    ),
    # Commodities
    (
        "GLD",
        "SPDR Gold Shares",
        "etf",
        "commodity",
        "Global",
        "index",
        "State Street",
    ),
    (
        "SLV",
        "iShares Silver Trust",
        "etf",
        "commodity",
        "Global",
        "index",
        "iShares",
    ),
    (
        "USO",
        "United States Oil Fund",
        "etf",
        "commodity",
        "Global",
        "index",
        "USCF",
    ),
    # Sector
    (
        "XLK",
        "Technology Select Sector SPDR",
        "etf",
        "equity",
        "US",
        "sector",
        "State Street",
    ),
    (
        "XLF",
        "Financial Select Sector SPDR",
        "etf",
        "equity",
        "US",
        "sector",
        "State Street",
    ),
    (
        "XLE",
        "Energy Select Sector SPDR",
        "etf",
        "equity",
        "US",
        "sector",
        "State Street",
    ),
    (
        "XLV",
        "Health Care Select Sector SPDR",
        "etf",
        "equity",
        "US",
        "sector",
        "State Street",
    ),
    # Multi-asset / Global
    (
        "VT",
        "Vanguard Total World Stock",
        "etf",
        "equity",
        "Global",
        "index",
        "Vanguard",
    ),
    (
        "ACWI",
        "iShares MSCI ACWI",
        "etf",
        "equity",
        "Global",
        "index",
        "iShares",
    ),
    # Real Estate
    (
        "VNQ",
        "Vanguard Real Estate",
        "etf",
        "equity",
        "US",
        "sector",
        "Vanguard",
    ),
    (
        "VNQI",
        "Vanguard Global ex-US RE",
        "etf",
        "equity",
        "Global ex-US",
        "sector",
        "Vanguard",
    ),
    # ── Temáticos / Innovación ───────────────
    ("ARKK", "ARK Innovation", "etf", "equity", "US", "thematic", "ARK"),
    (
        "ARKG",
        "ARK Genomic Revolution",
        "etf",
        "equity",
        "US",
        "thematic",
        "ARK",
    ),
    (
        "ICLN",
        "iShares Global Clean Energy",
        "etf",
        "equity",
        "Global",
        "thematic",
        "iShares",
    ),
    ("TAN", "Invesco Solar", "etf", "equity", "Global", "thematic", "Invesco"),
    (
        "KWEB",
        "KraneShares CSI China Internet",
        "etf",
        "equity",
        "China",
        "thematic",
        "Krane",
    ),
    (
        "HACK",
        "ETFMG Prime Cyber Security",
        "etf",
        "equity",
        "Global",
        "thematic",
        "ETFMG",
    ),
    (
        "BOTZ",
        "Global X Robotics & AI",
        "etf",
        "equity",
        "Global",
        "thematic",
        "Global X",
    ),
    (
        "ROBO",
        "ROBO Global Robotics & Auto",
        "etf",
        "equity",
        "Global",
        "thematic",
        "ROBO",
    ),
    (
        "GNOM",
        "Global X Genomics & Biotech",
        "etf",
        "equity",
        "Global",
        "thematic",
        "Global X",
    ),
    (
        "PBW",
        "Invesco WilderHill Clean Energy",
        "etf",
        "equity",
        "US",
        "thematic",
        "Invesco",
    ),
    (
        "FAN",
        "First Trust Global Wind Energy",
        "etf",
        "equity",
        "Global",
        "thematic",
        "First Trust",
    ),
    (
        "QCLN",
        "First Trust NASDAQ Clean Edge",
        "etf",
        "equity",
        "US",
        "thematic",
        "First Trust",
    ),
    (
        "MJ",
        "ETFMG Alternative Harvest",
        "etf",
        "equity",
        "Global",
        "thematic",
        "ETFMG",
    ),
    # ── Dividendos ───────────────────────────
    (
        "SCHD",
        "Schwab US Dividend Equity",
        "etf",
        "equity",
        "US",
        "dividend",
        "Schwab",
    ),
    (
        "JEPI",
        "JPMorgan Equity Premium Income",
        "etf",
        "equity",
        "US",
        "income",
        "JPMorgan",
    ),
    (
        "JEPQ",
        "JPMorgan Nasdaq Equity Premium",
        "etf",
        "equity",
        "US",
        "income",
        "JPMorgan",
    ),
    (
        "DGRO",
        "iShares Core Dividend Growth",
        "etf",
        "equity",
        "US",
        "dividend",
        "iShares",
    ),
    (
        "VIG",
        "Vanguard Dividend Appreciation",
        "etf",
        "equity",
        "US",
        "dividend",
        "Vanguard",
    ),
    (
        "DVY",
        "iShares Select Dividend",
        "etf",
        "equity",
        "US",
        "dividend",
        "iShares",
    ),
    (
        "SPHD",
        "Invesco S&P 500 High Dividend",
        "etf",
        "equity",
        "US",
        "dividend",
        "Invesco",
    ),
    # ── Semiconductores / Tech ───────────────
    (
        "SMH",
        "VanEck Semiconductor",
        "etf",
        "equity",
        "Global",
        "sector",
        "VanEck",
    ),
    (
        "SOXX",
        "iShares Semiconductor",
        "etf",
        "equity",
        "US",
        "sector",
        "iShares",
    ),
    (
        "IGV",
        "iShares Expanded Tech-Software",
        "etf",
        "equity",
        "US",
        "sector",
        "iShares",
    ),
    # ── Crypto ETFs ──────────────────────────
    (
        "BITO",
        "ProShares Bitcoin Strategy",
        "etf",
        "crypto",
        "US",
        "thematic",
        "ProShares",
    ),
    (
        "IBIT",
        "iShares Bitcoin Trust",
        "etf",
        "crypto",
        "US",
        "index",
        "iShares",
    ),
    (
        "ETHE",
        "Grayscale Ethereum Trust",
        "etf",
        "crypto",
        "US",
        "index",
        "Grayscale",
    ),
    (
        "GBTC",
        "Grayscale Bitcoin Trust",
        "etf",
        "crypto",
        "US",
        "index",
        "Grayscale",
    ),
    # ── Renta fija adicional ─────────────────
    (
        "SHY",
        "iShares 1-3 Year Treasury",
        "etf",
        "fixed_income",
        "US",
        "index",
        "iShares",
    ),
    (
        "IEF",
        "iShares 7-10 Year Treasury",
        "etf",
        "fixed_income",
        "US",
        "index",
        "iShares",
    ),
    (
        "GOVT",
        "iShares US Treasury Bond",
        "etf",
        "fixed_income",
        "US",
        "index",
        "iShares",
    ),
    (
        "VCSH",
        "Vanguard Short-Term Corp Bond",
        "etf",
        "fixed_income",
        "US",
        "index",
        "Vanguard",
    ),
    (
        "VCIT",
        "Vanguard Intermediate Corp Bond",
        "etf",
        "fixed_income",
        "US",
        "index",
        "Vanguard",
    ),
    (
        "TIPS",
        "iShares TIPS Bond",
        "etf",
        "fixed_income",
        "US",
        "index",
        "iShares",
    ),
    # ── EM / Intl renta fija ─────────────────
    (
        "EMB",
        "iShares JP Morgan USD EM Bond",
        "etf",
        "fixed_income",
        "EM",
        "index",
        "iShares",
    ),
    (
        "BNDX",
        "Vanguard Total Intl Bond",
        "etf",
        "fixed_income",
        "Global ex-US",
        "index",
        "Vanguard",
    ),
    (
        "IGOV",
        "iShares Intl Treasury Bond",
        "etf",
        "fixed_income",
        "Global ex-US",
        "index",
        "iShares",
    ),
    (
        "BWX",
        "SPDR Intl Treasury Bond",
        "etf",
        "fixed_income",
        "Global ex-US",
        "index",
        "State Street",
    ),
    (
        "PCY",
        "Invesco EM Sovereign Debt",
        "etf",
        "fixed_income",
        "EM",
        "index",
        "Invesco",
    ),
    # ── País / Región ────────────────────────
    (
        "VXUS",
        "Vanguard Total Intl Stock",
        "etf",
        "equity",
        "Global ex-US",
        "index",
        "Vanguard",
    ),
    (
        "IXUS",
        "iShares Core MSCI Total Intl",
        "etf",
        "equity",
        "Global ex-US",
        "index",
        "iShares",
    ),
    (
        "VGK",
        "Vanguard FTSE Europe",
        "etf",
        "equity",
        "Europe",
        "index",
        "Vanguard",
    ),
    (
        "VPL",
        "Vanguard FTSE Pacific",
        "etf",
        "equity",
        "Pacific",
        "index",
        "Vanguard",
    ),
    (
        "MCHI",
        "iShares MSCI China",
        "etf",
        "equity",
        "China",
        "index",
        "iShares",
    ),
    (
        "INDA",
        "iShares MSCI India",
        "etf",
        "equity",
        "India",
        "index",
        "iShares",
    ),
    (
        "EWJ",
        "iShares MSCI Japan",
        "etf",
        "equity",
        "Japan",
        "index",
        "iShares",
    ),
    (
        "EWZ",
        "iShares MSCI Brazil",
        "etf",
        "equity",
        "Brazil",
        "index",
        "iShares",
    ),
    (
        "EWG",
        "iShares MSCI Germany",
        "etf",
        "equity",
        "Germany",
        "index",
        "iShares",
    ),
    (
        "EWU",
        "iShares MSCI United Kingdom",
        "etf",
        "equity",
        "UK",
        "index",
        "iShares",
    ),
    (
        "EWY",
        "iShares MSCI South Korea",
        "etf",
        "equity",
        "South Korea",
        "index",
        "iShares",
    ),
    (
        "EWT",
        "iShares MSCI Taiwan",
        "etf",
        "equity",
        "Taiwan",
        "index",
        "iShares",
    ),
    (
        "EWH",
        "iShares MSCI Hong Kong",
        "etf",
        "equity",
        "Hong Kong",
        "index",
        "iShares",
    ),
    (
        "EWA",
        "iShares MSCI Australia",
        "etf",
        "equity",
        "Australia",
        "index",
        "iShares",
    ),
    (
        "EWC",
        "iShares MSCI Canada",
        "etf",
        "equity",
        "Canada",
        "index",
        "iShares",
    ),
    (
        "IEMG",
        "iShares Core MSCI EM",
        "etf",
        "equity",
        "Emerging Markets",
        "index",
        "iShares",
    ),
    (
        "IEFA",
        "iShares Core MSCI EAFE",
        "etf",
        "equity",
        "Developed ex-US",
        "index",
        "iShares",
    ),
    # ── Commodities ETFs ─────────────────────
    (
        "REMX",
        "VanEck Rare Earth/Strategic Metals",
        "etf",
        "commodity",
        "Global",
        "thematic",
        "VanEck",
    ),
    (
        "COPX",
        "Global X Copper Miners",
        "etf",
        "equity",
        "Global",
        "thematic",
        "Global X",
    ),
    (
        "CPER",
        "United States Copper Index",
        "etf",
        "commodity",
        "US",
        "index",
        "USCF",
    ),
    (
        "DBA",
        "Invesco DB Agriculture",
        "etf",
        "commodity",
        "Global",
        "index",
        "Invesco",
    ),
    (
        "DBC",
        "Invesco DB Commodity Index",
        "etf",
        "commodity",
        "Global",
        "index",
        "Invesco",
    ),
    (
        "PDBC",
        "Invesco Optimum Yield Diversified",
        "etf",
        "commodity",
        "Global",
        "index",
        "Invesco",
    ),
    (
        "GSG",
        "iShares S&P GSCI Commodity",
        "etf",
        "commodity",
        "Global",
        "index",
        "iShares",
    ),
    # ── Sector adicional ─────────────────────
    (
        "XLRE",
        "Real Estate Select Sector SPDR",
        "etf",
        "equity",
        "US",
        "sector",
        "State Street",
    ),
    (
        "XBI",
        "SPDR S&P Biotech",
        "etf",
        "equity",
        "US",
        "sector",
        "State Street",
    ),
    (
        "XOP",
        "SPDR S&P Oil & Gas Exploration",
        "etf",
        "equity",
        "US",
        "sector",
        "State Street",
    ),
    # ── Mutual Funds US ──────────────────────
    (
        "VFINX",
        "Vanguard 500 Index Investor",
        "mutual_fund",
        "equity",
        "US",
        "index",
        "Vanguard",
    ),
    (
        "FXAIX",
        "Fidelity 500 Index",
        "mutual_fund",
        "equity",
        "US",
        "index",
        "Fidelity",
    ),
    (
        "VTSAX",
        "Vanguard Total Stock Mkt Admiral",
        "mutual_fund",
        "equity",
        "US",
        "index",
        "Vanguard",
    ),
    (
        "VBTLX",
        "Vanguard Total Bond Mkt Admiral",
        "mutual_fund",
        "fixed_income",
        "US",
        "index",
        "Vanguard",
    ),
    (
        "VTIAX",
        "Vanguard Total Intl Stock Admiral",
        "mutual_fund",
        "equity",
        "Global ex-US",
        "index",
        "Vanguard",
    ),
    (
        "VWELX",
        "Vanguard Wellington",
        "mutual_fund",
        "multi_asset",
        "US",
        "balanced",
        "Vanguard",
    ),
    (
        "VTIVX",
        "Vanguard Target Retirement 2045",
        "mutual_fund",
        "multi_asset",
        "Global",
        "target_date",
        "Vanguard",
    ),
    (
        "PIMIX",
        "PIMCO Income Institutional",
        "mutual_fund",
        "fixed_income",
        "Global",
        "active",
        "PIMCO",
    ),
    (
        "DODFX",
        "Dodge & Cox International Stock",
        "mutual_fund",
        "equity",
        "Global ex-US",
        "active",
        "Dodge & Cox",
    ),
    (
        "FCNTX",
        "Fidelity Contrafund",
        "mutual_fund",
        "equity",
        "US",
        "active",
        "Fidelity",
    ),
]

_CSV_PATH = Path(__file__).resolve().parents[3] / "config" / "etf_universe.csv"


def _load_etfs_csv():
    """Cargar ETFs desde CSV si existe."""
    if not _CSV_PATH.exists():
        return None
    result = []
    with open(_CSV_PATH) as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) >= 7 and row[0].strip():
                result.append(tuple(c.strip() for c in row[:7]))
    return result or None


_csv_etfs = _load_etfs_csv()
if _csv_etfs:
    ETFS = _csv_etfs


class FundFetcher(BaseFetcher):
    """Descarga datos de ETFs/fondos."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "fund"
    RATE_LIMIT = 0.5

    def seed_funds(self) -> int:
        """Insertar ETFs de referencia."""
        session = get_session()
        count = 0
        try:
            for ticker, name, ftype, aclass, geo, strategy, provider in ETFS:
                if session.query(Fund).filter_by(ticker=ticker).first():
                    continue
                session.add(
                    Fund(
                        ticker=ticker,
                        name=name,
                        fund_type=ftype,
                        asset_class=aclass,
                        geography=geo,
                        strategy=strategy,
                        provider=provider,
                    )
                )
                count += 1
            session.commit()
        finally:
            session.close()
        return count

    def fetch_nav(
        self,
        ticker: str | None = None,
        period: str = "5y",
    ) -> dict[str, int]:
        """Descargar NAV histórico."""
        run_id = self._start_run(
            params={
                "ticker": ticker,
                "period": period,
            }
        )
        stats = {
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
        }
        session = get_session()

        try:
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            _ = src.id if src else None  # para auditoria futura

            if ticker:
                funds = [session.query(Fund).filter_by(ticker=ticker).first()]
            else:
                funds = session.query(Fund).all()

            for fund in funds:
                if not fund or not fund.ticker:
                    continue

                logger.info("  ETF: %s...", fund.ticker)
                try:
                    t = yf.Ticker(fund.ticker)
                    # auto_adjust=False: el NAV debe ser el valor
                    # liquidativo real, no el ajustado por
                    # distribuciones. Con el valor por defecto de
                    # yfinance, SPY figuraba a 461,39 el 2023-12-29
                    # cuando cerro a 475,31: un 2,93 % de desvio.
                    # Los ETF reparten dividendos, asi que aqui si
                    # importa; en indices, materias primas, crypto y
                    # divisas el ajuste no cambia nada.
                    df = t.history(period=period, auto_adjust=False)
                except Exception as e:
                    logger.warning(
                        "  Error %s: %s",
                        fund.ticker,
                        e,
                    )
                    stats["errors"] += 1
                    continue

                if df.empty:
                    continue

                # Actualizar expense ratio si hay info
                try:
                    info = t.info
                    if info:
                        er = info.get("annualReportExpenseRatio")
                        if er:
                            fund.expense_ratio = er
                        aum = info.get("totalAssets")
                        if aum:
                            fund.aum_usd = aum
                except Exception:
                    pass

                for idx, row in df.iterrows():
                    dt = idx.date()
                    close = row.get("Close")
                    if close is None:
                        continue

                    stats["fetched"] += 1
                    exists = (
                        session.query(NavDaily)
                        .filter(
                            and_(
                                NavDaily.fund_id == fund.id,
                                NavDaily.date == dt,
                            )
                        )
                        .first()
                    )

                    # Actualizar, no saltar: con el `continue` de antes
                    # un NAV mal cargado se quedaba para siempre y
                    # relanzar el fetcher no servia de nada.
                    if exists:
                        if float(exists.nav) != float(close):
                            exists.nav = float(close)
                            exists.source_id = self._source_id
                            exists.fetch_run_id = self._run_id
                            stats["updated"] += 1
                        continue

                    session.add(
                        NavDaily(
                            fund_id=fund.id,
                            date=dt,
                            nav=float(close),
                            volume=int(row.get("Volume", 0)) or None,
                            **self.linaje(),
                        )
                    )
                    stats["inserted"] += 1

                session.commit()

            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error funds: %s", e)
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats
