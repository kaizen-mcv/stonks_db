"""Fetcher para Yahoo Finance via yfinance."""

from datetime import datetime

import pandas as pd
import yaml
import yfinance as yf
from sqlalchemy import and_, text

# Importar todos los modelos para resolver FKs
import stonks.models  # noqa: F401
from stonks.config import settings
from stonks.db import engine, get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.equity import Company, PriceDaily
from stonks.models.meta import DataSource
from stonks.utils.batch import batch_download

UPSERT_CHUNK = 10_000


def _safe_float(val) -> float | None:
    """Convierte a float, None si NaN."""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return f
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    """Convierte a int, None si NaN."""
    f = _safe_float(val)
    if f is None:
        return None
    return int(f)


# S&P500 principales (top 50 por peso)
SP500_TOP = [
    "AAPL",
    "MSFT",
    "AMZN",
    "NVDA",
    "GOOGL",
    "META",
    "BRK-B",
    "TSLA",
    "UNH",
    "XOM",
    "JNJ",
    "JPM",
    "V",
    "PG",
    "MA",
    "HD",
    "CVX",
    "MRK",
    "ABBV",
    "LLY",
    "PEP",
    "KO",
    "COST",
    "AVGO",
    "WMT",
    "TMO",
    "MCD",
    "CSCO",
    "ACN",
    "ABT",
    "DHR",
    "CRM",
    "ADBE",
    "NFLX",
    "CMCSA",
    "TXN",
    "NEE",
    "PM",
    "WFC",
    "BMY",
    "AMD",
    "INTC",
    "ORCL",
    "UPS",
    "RTX",
    "QCOM",
    "AMGN",
    "HON",
    "IBM",
    "CAT",
]

# Europeas principales
EU_TOP = [
    "ASML",
    "MC.PA",
    "NVO",
    "SAP.DE",
    "SIE.DE",
    "OR.PA",
    "AZN.L",
    "SHEL.L",
    "NESN.SW",
    "ROG.SW",
    "NOVN.SW",
    "TTE.PA",
    "SAN.PA",
    "AIR.PA",
    "BNP.PA",
    "DTE.DE",
    "ALV.DE",
    "SAN.MC",
    "IBE.MC",
    "ITX.MC",
]


def load_tickers_from_yaml(
    region: str | None = None,
) -> list[str]:
    """Cargar tickers desde config/companies.yml.

    Args:
        region: Filtro por región (ej: 'europe_large',
            'asia_pacific'). None = todas.
    """
    yml = settings.config_dir / "companies.yml"
    if not yml.exists():
        return SP500_TOP + EU_TOP

    with open(yml, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if region and region in data:
        return data[region]

    # Todas las regiones
    tickers = []
    for _key, lst in data.items():
        tickers.extend(lst)
    return tickers


# Yahoo devuelve algunos mercados en la subunidad de su moneda, no en
# la moneda: Londres cotiza en peniques (GBp), Johannesburgo en
# centimos (ZAc) y Tel Aviv en agorot (ILA). Sin normalizar, AZN.L
# figuraba a 12.087 cuando AstraZeneca cotiza a 120 GBP, y `ZAc` ni
# siquiera existe en ref.currency, asi que la FK reventaba y el cron
# fallaba cada noche con esas empresas.
# (codigo de Yahoo) -> (moneda real, factor de division)
# Antiguedad maxima admisible del tipo de cambio, en dias. Un par
# que lleve mas de un mes sin actualizarse no sirve para convertir
# una capitalizacion de hoy.
MAX_ANTIGUEDAD_TIPO = 30

SUBUNIDADES = {
    "GBp": ("GBP", 100),
    "ZAc": ("ZAR", 100),
    "ILA": ("ILS", 100),
}

# Sufijo de ticker -> (moneda del mercado, divisor de subunidad).
# Londres cotiza en peniques, Johannesburgo en centimos y Tel Aviv en
# agorot.
SUBUNIDAD_POR_SUFIJO = {
    ".L": ("GBP", 100),
    ".JO": ("ZAR", 100),
    ".TA": ("ILS", 100),
}


def _normalizar_moneda(codigo: str | None) -> tuple[str | None, int]:
    """Devolver (moneda real, divisor) para una moneda de Yahoo."""
    if not codigo:
        return None, 1
    real, factor = SUBUNIDADES.get(codigo, (codigo, 1))
    return real, factor


def _sanear_ohlc(apertura, maximo, minimo, cierre):
    """Devolver un OHLC coherente, anulando lo que no lo sea.

    yfinance devuelve de vez en cuando un cierre fuera del rango del
    dia: HSBA.L el 2008-06-13 llega con open=high=low=7,198 y
    close=7,163. Es un artefacto de la fuente, no del calculo.

    Se conserva el cierre, que es el valor que importa y el unico
    obligatorio, y se anulan las otras tres columnas en lugar de
    inventar un rango que las contenga. Es la misma politica que
    aplico la migracion que limpio las filas historicas.
    """
    valores = [v for v in (apertura, maximo, minimo) if v is not None]
    if not valores or cierre is None:
        return apertura, maximo, minimo

    coherente = (
        (maximo is None or minimo is None or maximo >= minimo)
        and (minimo is None or cierre >= minimo)
        and (maximo is None or cierre <= maximo)
        and (
            apertura is None
            or minimo is None
            or maximo is None
            or minimo <= apertura <= maximo
        )
    )
    if coherente:
        return apertura, maximo, minimo
    return None, None, None


def _escalar(valor, divisor: int):
    """Pasar un precio de subunidad a moneda, tolerando nulos."""
    numero = _safe_float(valor)
    return None if numero is None else numero / divisor


class YFinanceFetcher(BaseFetcher):
    """Descarga precios e info de empresas desde
    Yahoo Finance."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "equity"
    RATE_LIMIT = 0.5

    def fetch_company_info(self, ticker: str) -> Company | None:
        """Obtener/actualizar info de una empresa."""
        session = get_session()
        try:
            t = yf.Ticker(ticker)
            info = t.info
            if not info or "symbol" not in info:
                logger.warning("Sin datos para %s", ticker)
                return None

            company = session.query(Company).filter_by(ticker=ticker).first()

            if not company:
                company = Company(
                    ticker=ticker,
                    name=info.get(
                        "longName",
                        info.get("shortName", ticker),
                    ),
                    currency_code=_normalizar_moneda(
                        info.get("currency")
                    )[0],
                    market_cap_usd=self._a_usd(
                        session,
                        info.get("marketCap"),
                        info.get("currency"),
                    ),
                    shares_outstanding=info.get("sharesOutstanding"),
                    website=info.get("website"),
                    description=info.get("longBusinessSummary"),
                    employees=info.get("fullTimeEmployees"),
                    is_active=True,
                    country_code=self._resolve_country(
                        info.get("country", "")
                    ),
                )
                session.add(company)
            else:
                # La rama de actualizacion no fijaba la moneda, asi
                # que las empresas ya creadas se quedaban con
                # `currency_code` a nulo para siempre.
                company.currency_code = _normalizar_moneda(
                    info.get("currency")
                )[0]
                company.market_cap_usd = self._a_usd(
                    session,
                    info.get("marketCap"),
                    info.get("currency"),
                )
                company.shares_outstanding = info.get("sharesOutstanding")
                company.last_updated = datetime.now()

            session.commit()
            result = company.id
            session.close()
            return result
        except Exception as e:
            session.rollback()
            logger.error("Error info %s: %s", ticker, e)
            session.close()
            return None

    @staticmethod
    def _a_usd(session, importe, moneda: str | None):
        """Convertir un importe a dolares con el ultimo tipo de cambio.

        yfinance devuelve `marketCap` en la moneda de cotizacion, pero
        la columna se llama `market_cap_usd`. Toyota figuraba con 34,5
        billones, que son yenes: la media de las coreanas salia a
        148.667 "miles de millones de dolares". Aqui se convierte de
        verdad, para que la columna signifique lo que dice su nombre.

        Si no hay tipo de cambio para esa moneda se devuelve None en
        lugar del importe sin convertir: es preferible no tener dato a
        tener uno que miente sobre su unidad.
        """
        if importe is None:
            return None

        # Ojo con la asimetria de Yahoo: para Londres cotiza los
        # PRECIOS en peniques pero informa la CAPITALIZACION en libras,
        # aunque el campo `currency` diga GBp en ambos casos.
        # Comprobado: AstraZeneca sale con marketCap 187.460.829.184,
        # que son 187 mil millones de libras, no de peniques. Aqui
        # solo se traduce el codigo de moneda, sin dividir.
        moneda, _ = _normalizar_moneda(moneda)
        importe = float(importe)

        if not moneda or moneda == "USD":
            return importe

        # El par puede estar guardado en cualquiera de los dos
        # sentidos: USDJPY existe, pero el euro y el dolar australiano
        # se cotizan al reves (EURUSD, AUDUSD). Se admite el invertido
        # y se toma su reciproco.
        # La capitalizacion es una foto de hoy, asi que se convierte
        # con el tipo de cambio vigente. Se exige que sea reciente: un
        # tipo de hace anos convertiria mal y en silencio.
        tipo = session.execute(
            text(
                "SELECT r.close FROM forex.rate_daily r "
                "JOIN forex.currency_pair p ON p.id = r.pair_id "
                "WHERE p.base_currency = 'USD' "
                "AND p.quote_currency = :m "
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

        if not tipo or float(tipo) <= 0:
            logger.warning(
                "Sin tipo de cambio USD/%s de los ultimos %d dias: "
                "capitalizacion sin convertir",
                moneda,
                MAX_ANTIGUEDAD_TIPO,
            )
            return None
        return float(importe) / float(tipo)

    @staticmethod
    def _divisores(ticker_to_id: dict) -> dict:
        """Divisor de subunidad para cada company_id.

        El sufijo del ticker dice en que mercado cotiza el valor, pero
        no basta por si solo: en la Bolsa de Londres hay valores que
        Yahoo devuelve en dolares o en euros, no en peniques. Compass
        Group acabo figurando a 0,33 —cotiza sobre 24 libras— porque
        se le dividio por 100 un precio que ya venia en dolares, y
        Metlen igual con euros.

        Asi que se divide solo cuando la moneda declarada por Yahoo es
        la del mercado, o cuando no se conoce (que es el caso de la
        mayoria y donde el sufijo sigue siendo la mejor pista).
        """
        salida = {}
        with get_session() as session:
            monedas = dict(
                session.execute(
                    text(
                        "SELECT ticker, currency_code "
                        "FROM equity.company WHERE ticker = ANY(:t)"
                    ),
                    {"t": list(ticker_to_id)},
                ).fetchall()
            )

        for ticker, cid in ticker_to_id.items():
            for sufijo, (moneda, divisor) in SUBUNIDAD_POR_SUFIJO.items():
                if not ticker.upper().endswith(sufijo):
                    continue
                declarada = monedas.get(ticker)
                if declarada in (None, moneda):
                    salida[cid] = divisor
                break
        return salida

    def fetch_prices(
        self,
        ticker: str,
        period: str = "5y",
        company_id: int | None = None,
    ) -> dict[str, int]:
        """Descargar precios históricos OHLCV.

        Args:
            ticker: Símbolo bursátil
            period: Período (1y, 5y, 10y, max)
            company_id: ID si ya se conoce

        Returns:
            {"fetched": N, "inserted": N, "updated": N}
        """
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
            # Obtener source_id
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            src_id = src.id if src else None

            # Obtener company_id si no se proporcionó
            if company_id is None:
                comp = session.query(Company).filter_by(ticker=ticker).first()
                if not comp:
                    # Crear empresa primero
                    session.close()
                    company_id = self.fetch_company_info(ticker)
                    session = get_session()
                    if not company_id:
                        self._finish_run(
                            run_id,
                            "failed",
                            error_log={"msg": "No se pudo crear empresa"},
                        )
                        session.close()
                        return stats
                else:
                    company_id = comp.id

            # Descargar datos
            t = yf.Ticker(ticker)
            # auto_adjust=False: `Close` es el cierre real y
            # `Adj Close` el ajustado. Con el valor por defecto de
            # yfinance (True) solo llega el ajustado y sin etiquetar.
            df = t.history(period=period, auto_adjust=False)
            # Londres cotiza en peniques y Johannesburgo en centimos.
            div = self._divisores({ticker: 0}).get(0, 1)

            if df.empty:
                logger.warning("Sin precios para %s", ticker)
                self._finish_run(run_id, "success", **stats)
                session.close()
                return stats

            for idx, row in df.iterrows():
                dt = idx.date()
                stats["fetched"] += 1

                existing = (
                    session.query(PriceDaily)
                    .filter(
                        and_(
                            PriceDaily.company_id == company_id,
                            PriceDaily.date == dt,
                        )
                    )
                    .first()
                )

                if existing:
                    if float(existing.close) != float(row["Close"]) / div:
                        cierre = float(row["Close"]) / div
                        ap, mx, mn = _sanear_ohlc(
                            _escalar(row.get("Open"), div),
                            _escalar(row.get("High"), div),
                            _escalar(row.get("Low"), div),
                            cierre,
                        )
                        existing.open = ap
                        existing.high = mx
                        existing.low = mn
                        existing.close = cierre
                        existing.adj_close = _escalar(
                            row.get("Adj Close"), div
                        )
                        existing.volume = row.get("Volume")
                        stats["updated"] += 1
                else:
                    session.add(
                        PriceDaily(
                            company_id=company_id,
                            date=dt,
                            **dict(
                                zip(
                                    ("open", "high", "low"),
                                    _sanear_ohlc(
                                        _escalar(row.get("Open"), div),
                                        _escalar(row.get("High"), div),
                                        _escalar(row.get("Low"), div),
                                        float(row["Close"]) / div,
                                    ),
                                    strict=True,
                                )
                            ),
                            close=float(row["Close"]) / div,
                            adj_close=_escalar(row.get("Adj Close"), div),
                            volume=int(row.get("Volume", 0)),
                            source_id=src_id,
                        )
                    )
                    stats["inserted"] += 1

            session.commit()
            self._finish_run(run_id, "success", **stats)

        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error precios %s: %s", ticker, e)
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats

    def fetch_batch(
        self,
        tickers: list[str] | None = None,
        period: str = "5y",
    ) -> dict[str, dict]:
        """Descargar precios para múltiples tickers."""
        if tickers is None:
            tickers = SP500_TOP

        results = {}
        total = len(tickers)
        for i, ticker in enumerate(tickers, 1):
            logger.info(
                "[%d/%d] Descargando %s...",
                i,
                total,
                ticker,
            )
            # Primero info de la empresa
            company_id = self.fetch_company_info(ticker)
            # Luego precios
            results[ticker] = self.fetch_prices(
                ticker,
                period=period,
                company_id=company_id,
            )
            ins = results[ticker]["inserted"]
            upd = results[ticker]["updated"]
            logger.info(
                "  → %s: %d insertados, %d actualizados",
                ticker,
                ins,
                upd,
            )

        return results

    def fetch_prices_bulk(
        self,
        tickers: list[str],
        period: str = "max",
    ) -> dict[str, int]:
        """Descarga batch + upsert masivo SQL.

        Usa yf.download() para descargar en lotes y
        INSERT...ON CONFLICT DO UPDATE para upsert
        en chunks de UPSERT_CHUNK filas.

        Returns:
            {"fetched": N, "upserted": N, "errors": N}
        """
        run_id = self._start_run(
            params={
                "tickers_count": len(tickers),
                "period": period,
                "mode": "bulk",
            }
        )
        stats = {
            "fetched": 0,
            "upserted": 0,
            "errors": 0,
        }

        try:
            # Mapa ticker → company_id
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT ticker, id FROM equity.company")
                ).fetchall()
            ticker_to_id = {r[0]: r[1] for r in rows}

            # Obtener source_id
            with engine.connect() as conn:
                src = conn.execute(
                    text(
                        "SELECT id FROM meta.data_source "
                        "WHERE name = 'yfinance' LIMIT 1"
                    )
                ).scalar()
            src_id = src

            # Descarga batch
            # auto_adjust=False para que `close` sea el cierre
            # real y `adj_close` el ajustado por splits y
            # dividendos. Con el valor por defecto de yfinance
            # (True) `close` venia ya ajustado y no habia
            # columna "Adj Close": las 24 M de filas de
            # adj_close estaban vacias y los ajustes
            # retroactivos generaban precios negativos.
            df = batch_download(
                tickers,
                period=period,
                interval="1d",
                auto_adjust=False,
            )
            if df.empty:
                logger.warning("batch_download vacío")
                self._finish_run(run_id, "success", **stats)
                return stats

            stats["fetched"] = len(df)

            # Divisor por ticker: los mercados que cotizan en
            # subunidades (Londres en peniques, Johannesburgo en
            # centimos) hay que pasarlos a la moneda, o AZN.L figura a
            # 12.087 cuando AstraZeneca vale 120 GBP.
            divisor_por_id = self._divisores(ticker_to_id)

            # Preparar filas para upsert
            upsert_rows = []
            for _, row in df.iterrows():
                ticker = row.get("Ticker", "")
                cid = ticker_to_id.get(ticker)
                if cid is None:
                    continue
                div = divisor_por_id.get(cid, 1)
                close = row.get("Close")
                if close is None or (
                    hasattr(close, "__float__") and str(close) == "nan"
                ):
                    continue
                dt = row.get("ts")
                if dt is None or pd.isna(dt):
                    continue
                if hasattr(dt, "date"):
                    dt = dt.date()
                upsert_rows.append(
                    {
                        "company_id": cid,
                        "date": dt,
                        **dict(
                            zip(
                                ("open", "high", "low"),
                                _sanear_ohlc(
                                    _escalar(row.get("Open"), div),
                                    _escalar(row.get("High"), div),
                                    _escalar(row.get("Low"), div),
                                    float(close) / div,
                                ),
                                strict=True,
                            )
                        ),
                        "close": float(close) / div,
                        "adj_close": _escalar(row.get("Adj Close"), div),
                        "volume": _safe_int(row.get("Volume")),
                        "source_id": src_id,
                        "fetch_run_id": run_id,
                    }
                )

            # Upsert en chunks
            upsert_sql = text("""
                INSERT INTO equity.price_daily
                    (company_id, date, open, high, low,
                     close, adj_close, volume, source_id,
                     fetch_run_id)
                VALUES
                    (:company_id, :date, :open, :high,
                     :low, :close, :adj_close, :volume, :source_id,
                     :fetch_run_id)
                ON CONFLICT (company_id, date) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    adj_close = EXCLUDED.adj_close,
                    volume = EXCLUDED.volume,
                    source_id = EXCLUDED.source_id,
                    fetch_run_id = EXCLUDED.fetch_run_id
            """)

            total_rows = len(upsert_rows)
            with engine.begin() as conn:
                for j in range(0, total_rows, UPSERT_CHUNK):
                    chunk = upsert_rows[j : j + UPSERT_CHUNK]
                    conn.execute(upsert_sql, chunk)
                    stats["upserted"] += len(chunk)
                    logger.info(
                        "Upsert %d/%d filas",
                        stats["upserted"],
                        total_rows,
                    )

            self._finish_run(
                run_id,
                "success",
                fetched=stats["fetched"],
                inserted=stats["upserted"],
            )

        except Exception as e:
            stats["errors"] += 1
            logger.error("Error bulk: %s", e)
            # `stats` usa la clave "upserted" y _finish_run espera
            # "inserted": pasar **stats hacia el manejador reventaba
            # con un TypeError que tapaba el error de verdad.
            self._finish_run(
                run_id,
                "failed",
                fetched=stats["fetched"],
                inserted=stats["upserted"],
                errors=stats["errors"],
                error_log={"msg": str(e)},
            )

        return stats

    @staticmethod
    def _resolve_country(
        country_name: str,
    ) -> str | None:
        """Convertir nombre de país a ISO alpha-3."""
        import pycountry

        if not country_name:
            return None
        try:
            c = pycountry.countries.lookup(country_name)
            return c.alpha_3
        except LookupError:
            return None
