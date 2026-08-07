"""Fetcher de precios diarios via Tiingo: segunda fuente de precios.

La base de datos dependia de un unico proveedor de precios (yfinance),
que no tiene API oficial ni acuerdo de servicio. Tiingo publica el
historico EOD completo con una clave gratuita
(https://www.tiingo.com/account/api/token) y si tiene API documentada.

Se descarto Stooq, que era la alternativa sin clave: desde 2026 responde
a cualquier peticion programatica con un desafio JavaScript de
verificacion de navegador, y saltarselo seria evadir una medida
antibot deliberada.

Este fetcher no sustituye a yfinance, lo complementa:

1. **Relleno de huecos**: inserta solo las fechas ausentes
   (`ON CONFLICT DO NOTHING`), de modo que yfinance sigue siendo la
   fuente primaria y Tiingo tapa los agujeros.
2. **Validacion cruzada**: compara cierres de ambas fuentes y registra
   las divergencias en `meta.data_quality`, lo que permite detectar
   splits mal aplicados o series corruptas.

Limites del plan gratuito: 1.000 peticiones/hora, 500 simbolos unicos
al mes. Por eso `fetch_prices` acepta `limite` y conviene rotar el
universo en vez de barrerlo entero.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import requests
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from stonks.config import settings
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.equity import PriceDaily
from stonks.models.meta import DataQuality, DataSource

BASE_URL = "https://api.tiingo.com/tiingo/daily"
CHUNK = 5000

# Divergencia de cierre a partir de la cual se registra un aviso.
UMBRAL_DIVERGENCIA = Decimal("0.02")  # 2 %

# Umbral del cruce entre fuentes, en porcentaje. Dos proveedores
# no dan exactamente el mismo cierre —difieren en el mercado que
# consideran oficial y en los redondeos—, pero un 1 % ya es mucho
# para un cierre diario.
TOLERANCIA_CRUCE_PCT = 1.0

# Tiingo cubre principalmente mercados estadounidenses. Se procesan
# solo empresas de esas bolsas en lugar de gastar cuota en simbolos
# que se sabe que devolveran 404.
MIC_CUBIERTOS = {"XNYS", "XNAS"}


class SinClaveTiingo(RuntimeError):
    """La clave de API no esta configurada."""


class TiingoFetcher(BaseFetcher):
    """Precios diarios de Tiingo como fuente secundaria."""

    SOURCE_NAME = "tiingo"
    DOMAIN = "equity"
    RATE_LIMIT = 1.0

    def __init__(self) -> None:
        super().__init__()
        self.token = settings.tiingo_key
        if self.token:
            self._session.headers.update(
                {"Authorization": f"Token {self.token}"}
            )

    def _exigir_clave(self) -> None:
        if not self.token:
            raise SinClaveTiingo(
                "Falta STONKS_TIINGO_KEY en .env. Clave gratuita en "
                "https://www.tiingo.com/account/api/token"
            )

    def fetch_prices(
        self,
        ticker: str | None = None,
        limite: int | None = None,
        desde: str = "1990-01-01",
        solo_huecos: bool = True,
    ) -> dict:
        """Descargar precios y rellenar huecos de equity.price_daily.

        Args:
            ticker: procesar solo esta empresa; si es None, recorre el
                universo cubierto por Tiingo.
            limite: maximo de empresas (importante: la cuota gratuita
                permite 500 simbolos unicos al mes).
            desde: fecha inicial del historico.
            solo_huecos: si es True (por defecto) no pisa datos ya
                existentes; solo inserta fechas ausentes.

        Returns:
            {"empresas": N, "puntos": N, "errores": N}
        """
        self._exigir_clave()

        session = get_session()
        run_id = self._start_run({"ticker": ticker, "limite": limite})
        src_id = self._ensure_source(session)

        total = 0
        errores = 0
        procesadas = 0

        try:
            empresas = self._empresas_objetivo(session, ticker, limite)
            logger.info("Tiingo: %d empresas a procesar", len(empresas))

            for company_id, tk in empresas:
                n = self._fetch_empresa(
                    session, company_id, tk, src_id, desde, solo_huecos
                )
                if n < 0:
                    errores += 1
                else:
                    total += n
                    procesadas += 1

            self._finish_run(
                run_id,
                "success",
                fetched=total,
                inserted=total,
                errors=errores,
            )
            logger.info(
                "Tiingo: %d empresas, %d puntos nuevos, %d errores",
                procesadas,
                total,
                errores,
            )
        except Exception as e:
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("Tiingo fallo: %s", e)
            raise
        finally:
            session.close()

        return {
            "empresas": procesadas,
            "puntos": total,
            "errores": errores,
        }

    def validar(self, limite: int = 50) -> dict:
        """Comparar cierres de Tiingo con los ya cargados.

        No escribe precios: registra en `meta.data_quality` las empresas
        cuyo ultimo cierre diverge mas del umbral. Sirve para detectar
        splits no aplicados o series corruptas.

        Returns:
            {"comparadas": N, "divergentes": N}
        """
        self._exigir_clave()

        session = get_session()
        comparadas = 0
        divergentes = 0

        try:
            for company_id, tk in self._empresas_objetivo(
                session, None, limite
            ):
                filas = self._descargar(tk, desde=None)
                if not filas:
                    continue

                ultima = filas[-1]
                propio = session.execute(
                    text(
                        "SELECT close FROM equity.price_daily "
                        "WHERE company_id = :cid AND date = :d"
                    ),
                    {"cid": company_id, "d": ultima["date"]},
                ).scalar()

                if propio is None:
                    continue

                referencia = ultima["close"]
                if not referencia:
                    continue

                comparadas += 1
                desvio = abs(propio - referencia) / referencia
                if desvio <= UMBRAL_DIVERGENCIA:
                    continue

                divergentes += 1
                logger.warning(
                    "%s (%s): cierre propio %s vs Tiingo %s (%.1f%%)",
                    tk,
                    ultima["date"],
                    propio,
                    referencia,
                    desvio * 100,
                )
                self._registrar_calidad(session, tk, desvio)

            session.commit()
        finally:
            session.close()

        logger.info(
            "Tiingo validacion: %d comparadas, %d divergentes",
            comparadas,
            divergentes,
        )
        return {"comparadas": comparadas, "divergentes": divergentes}

    # ── Internos ─────────────────────────────────

    @staticmethod
    def _empresas_objetivo(
        session, ticker: str | None, limite: int | None
    ) -> list[tuple[int, str]]:
        """Empresas de bolsas cubiertas por Tiingo.

        Se priorizan las que tienen menos historico cargado: son las que
        mas se benefician del relleno de huecos.
        """
        sql = (
            "SELECT c.id, c.ticker "
            "FROM equity.company c "
            "LEFT JOIN ref.exchange e ON e.id = c.exchange_id "
            "WHERE c.ticker IS NOT NULL "
        )
        params: dict = {}
        if ticker:
            sql += "AND c.ticker = :tk "
            params["tk"] = ticker
        else:
            sql += (
                "AND (e.mic = ANY(:mics) OR c.exchange_id IS NULL) "
                "ORDER BY ("
                "  SELECT count(*) FROM equity.price_daily p "
                "  WHERE p.company_id = c.id"
                ") ASC "
            )
            params["mics"] = list(MIC_CUBIERTOS)
        if limite:
            sql += "LIMIT :lim"
            params["lim"] = limite

        return [
            (row[0], row[1])
            for row in session.execute(text(sql), params).fetchall()
        ]

    def _descargar(self, ticker: str, desde: str | None) -> list[dict]:
        """Descargar el historico diario de un ticker.

        Returns:
            Lista de dicts con date/open/high/low/close/adj_close/volume.
        """
        url = f"{BASE_URL}/{ticker.lower()}/prices"
        params = {"format": "json"}
        if desde:
            params["startDate"] = desde

        self._rate_limit()
        try:
            resp = self._session.get(url, params=params, timeout=30)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            datos = resp.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning("Tiingo %s: %s", ticker, e)
            return []

        if not isinstance(datos, list):
            return []

        filas = []
        for d in datos:
            fecha = self._fecha(d.get("date"))
            # `close` es el cierre real y `adjClose` el ajustado por
            # dividendos y splits. Antes se guardaba el ajustado en la
            # columna `close`, que es el mismo defecto que tenia
            # yfinance con `auto_adjust=True`: SPY figuraba a 461,39 el
            # 29/12/2023 cuando cerro a 475,31. Y aqui pesa mas, porque
            # Tiingo rellena huecos en la MISMA columna que yfinance:
            # media serie quedaria ajustada y la otra media no.
            cierre = self._dec(d.get("close"))
            if fecha is None or cierre is None:
                continue
            filas.append(
                {
                    "date": fecha,
                    "open": self._dec(d.get("open")),
                    "high": self._dec(d.get("high")),
                    "low": self._dec(d.get("low")),
                    "close": cierre,
                    "adj_close": self._dec(d.get("adjClose")),
                    "volume": self._entero(d.get("volume")),
                }
            )
        filas.sort(key=lambda f: f["date"])
        return filas

    @staticmethod
    def _fecha(valor) -> date | None:
        if not valor:
            return None
        try:
            return datetime.fromisoformat(
                str(valor).replace("Z", "+00:00")
            ).date()
        except ValueError:
            return None

    @staticmethod
    def _dec(valor) -> Decimal | None:
        if valor is None:
            return None
        try:
            return round(Decimal(str(valor)), 4)
        except InvalidOperation:
            return None

    @staticmethod
    def _entero(valor) -> int | None:
        try:
            return int(float(valor)) if valor is not None else None
        except (ValueError, TypeError):
            return None

    def _fetch_empresa(
        self,
        session,
        company_id: int,
        ticker: str,
        src_id: int,
        desde: str,
        solo_huecos: bool,
    ) -> int:
        """Cargar el historico de una empresa. -1 si error."""
        filas = self._descargar(ticker, desde)
        if not filas:
            return -1

        lote = [
            {
                "company_id": company_id,
                "date": f["date"],
                "open": f["open"],
                "high": f["high"],
                "low": f["low"],
                "close": f["close"],
                "adj_close": f["adj_close"],
                "volume": f["volume"],
                "source_id": src_id,
            }
            for f in filas
        ]

        insertadas = 0
        for i in range(0, len(lote), CHUNK):
            trozo = lote[i : i + CHUNK]
            stmt = insert(PriceDaily).values(trozo)
            if solo_huecos:
                # yfinance manda: Tiingo solo rellena fechas ausentes.
                stmt = stmt.on_conflict_do_nothing(
                    constraint="price_daily_company_id_date_key"
                )
            else:
                stmt = stmt.on_conflict_do_update(
                    constraint="price_daily_company_id_date_key",
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "adj_close": stmt.excluded.adj_close,
                        "volume": stmt.excluded.volume,
                        "source_id": stmt.excluded.source_id,
                    },
                )
            insertadas += session.execute(stmt).rowcount or 0

        session.commit()
        if insertadas:
            logger.info("  %s: %d puntos nuevos", ticker, insertadas)
        return insertadas

    @staticmethod
    def _registrar_calidad(session, ticker: str, desvio: Decimal) -> None:
        """Anotar una divergencia de precio en meta.data_quality."""
        fila = (
            session.query(DataQuality)
            .filter_by(
                domain="equity",
                entity_type="price_divergence",
                entity_id=ticker,
            )
            .first()
        )
        if not fila:
            fila = DataQuality(
                domain="equity",
                entity_type="price_divergence",
                entity_id=ticker,
            )
            session.add(fila)
        fila.completeness_score = float(1 - min(desvio, Decimal("1")))
        fila.source_count = 2
        fila.last_assessed = datetime.now()

    @staticmethod
    def _ensure_source(session) -> int:
        """Registrar Tiingo en meta.data_source si falta."""
        src = session.query(DataSource).filter_by(name="tiingo").first()
        if not src:
            src = DataSource(
                name="tiingo",
                display_name="Tiingo (precios EOD)",
                base_url=BASE_URL,
                api_key_env_var="STONKS_TIINGO_KEY",
                rate_limit_per_second=1.0,
                is_enabled=True,
                notes=(
                    "Fuente secundaria de precios: rellena huecos de "
                    "yfinance y permite validacion cruzada. Plan "
                    "gratuito: 1.000 peticiones/hora, 500 simbolos "
                    "unicos al mes."
                ),
            )
            session.add(src)
            session.commit()
        return src.id

    def comparar_precios(
        self,
        muestra: int = 20,
        dias: int = 10,
    ) -> dict:
        """Comparar precios guardados contra los de Tiingo.

        Es la validacion cruzada que el proyecto no tenia: hasta ahora
        todos los precios venian de yfinance, asi que un error suyo era
        indetectable desde dentro. Aqui se pide a una segunda fuente
        los ultimos cierres de una muestra y se mide la diferencia.

        La muestra rota con el dia del mes para no gastar siempre la
        cuota gratuita en las mismas empresas.

        Returns:
            {"comparados": N, "divergentes": N, "peor": {...}}
        """
        self._exigir_clave()

        desde = (date.today() - timedelta(days=dias)).isoformat()
        session = get_session()
        salida = {"comparados": 0, "divergentes": 0, "peor": None}

        try:
            # Solo cotizadas estadounidenses: Tiingo cubre mal el resto
            # y una divergencia por cobertura no dice nada de la carga.
            empresas = session.execute(
                text(
                    "SELECT c.id, c.ticker FROM equity.company c "
                    "WHERE c.ticker !~ '\\.' AND c.is_active "
                    "ORDER BY (c.id + :giro) % 1000, c.id "
                    "LIMIT :n"
                ),
                {"n": muestra, "giro": date.today().day},
            ).fetchall()

            for company_id, ticker in empresas:
                nuestros = dict(
                    session.execute(
                        text(
                            "SELECT date, close FROM equity.price_daily "
                            "WHERE company_id = :c AND date >= :d"
                        ),
                        {"c": company_id, "d": desde},
                    ).fetchall()
                )
                if not nuestros:
                    continue

                for fila in self._descargar(ticker, desde):
                    nuestro = nuestros.get(fila["date"])
                    if nuestro is None or not nuestro:
                        continue
                    suyo = fila["close"]
                    if suyo is None or float(suyo) == 0:
                        continue

                    desvio = abs(
                        float(nuestro) - float(suyo)
                    ) / float(suyo) * 100
                    salida["comparados"] += 1
                    if desvio > TOLERANCIA_CRUCE_PCT:
                        salida["divergentes"] += 1
                        peor = salida["peor"]
                        if peor is None or desvio > peor["desvio_pct"]:
                            salida["peor"] = {
                                "ticker": ticker,
                                "fecha": str(fila["date"]),
                                "nuestro": float(nuestro),
                                "tiingo": float(suyo),
                                "desvio_pct": round(desvio, 3),
                            }
                        logger.warning(
                            "Cruce %s %s: %.4f nuestro vs %.4f Tiingo "
                            "(%.2f%%)",
                            ticker,
                            fila["date"],
                            float(nuestro),
                            float(suyo),
                            desvio,
                        )
        finally:
            session.close()

        logger.info(
            "Cruce con Tiingo: %d precios comparados, %d divergen",
            salida["comparados"],
            salida["divergentes"],
        )
        return salida
