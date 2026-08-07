"""Fetcher de constituyentes de los indices bursatiles mundiales.

La auditoria encontro que `equity.company` era un 86 % estadounidense
(8.985 de 10.491), con China en 36 empresas e India en 49. Eso no es
una base de datos de economia mundial en renta variable: es una base de
Estados Unidos con anexos.

La causa era que solo el S&P 500 tenia constituyentes cargados
(`constituents.py`); los otros 27 indices declarados en
`equity.market_index` estaban a cero.

Este fetcher los rellena desde las paginas de Wikipedia de cada indice,
que publican la lista con el ticker ya en el formato que espera
yfinance (sufijo de mercado incluido: ADS.DE, AC.PA, ACS.MC...). Cuando
la pagina da el ticker local sin sufijo, se anade el de la bolsa.
"""

import io
import re

import pandas as pd
import requests
from sqlalchemy import text

from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.meta import DataSource

WIKI = "https://en.wikipedia.org/wiki/"

# (codigo indice, pagina de Wikipedia, sufijo yfinance, MIC de la bolsa)
# El sufijo va vacio cuando la pagina ya lo incluye en el ticker.
INDICES = [
    ("DAX", "DAX", "", "XETR"),
    ("CAC40", "CAC_40", "", "XPAR"),
    ("IBEX35", "IBEX_35", "", "XMAD"),
    ("FTSE100", "FTSE_100_Index", ".L", "XLON"),
    ("FTSEMIB", "FTSE_MIB", ".MI", "XMIL"),
    ("AEX", "AEX_index", ".AS", "XAMS"),
    ("SMI", "Swiss_Market_Index", ".SW", "XSWX"),
    ("NIKKEI", "Nikkei_225", ".T", "XTKS"),
    ("HSI", "Hang_Seng_Index", ".HK", "XHKG"),
    ("KOSPI", "KOSPI", ".KS", "XKRX"),
    ("TSX", "S%26P/TSX_60", ".TO", "XTSE"),
    ("ASX200", "S%26P/ASX_200", ".AX", "XASX"),
    ("SENSEX", "BSE_SENSEX", ".NS", "XNSE"),
    ("BOVESPA", "List_of_companies_listed_on_B3", ".SA", "XBSP"),
    ("STOXX50", "EURO_STOXX_50", "", None),
    ("JSEAS", "FTSE/JSE_Top_40_Index", ".JO", "XJSE"),
    ("BIST100", "BIST_100", ".IS", "XIST"),
    ("IPC", "Indice_de_Precios_y_Cotizaciones", ".MX", "XMEX"),
]

# Nombres de columna que contienen el simbolo, por orden de preferencia.
COLUMNAS_TICKER = ("ticker", "symbol", "epic", "code", "ric")
COLUMNAS_NOMBRE = ("company", "name", "constituent", "issue")

# Un ticker plausible: letras, digitos, punto y guion.
PATRON_TICKER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,15}$")


class IndexConstituentsFetcher(BaseFetcher):
    """Constituyentes de los indices bursatiles no estadounidenses."""

    SOURCE_NAME = "wikipedia_indices"
    DOMAIN = "equity"
    RATE_LIMIT = 1.5

    def fetch(
        self,
        indices: list[str] | None = None,
        con_precios: bool = False,
    ) -> dict:
        """Cargar constituyentes y dar de alta las empresas nuevas.

        Args:
            indices: subconjunto de codigos de indice. Si es None se
                recorren todos los de `INDICES`.
            con_precios: si es True, descarga tambien el historico de
                precios de cada empresa nueva (lento).

        Returns:
            {"indices": N, "empresas_nuevas": N, "vinculos": N,
             "sin_tabla": [...]}
        """
        session = get_session()
        run_id = self._start_run({"indices": indices})
        src_id = self._ensure_source(session)

        nuevas = 0
        vinculos = 0
        procesados = 0
        sin_tabla = []

        try:
            for codigo, pagina, sufijo, mic in INDICES:
                if indices and codigo not in indices:
                    continue

                filas = self._extraer(pagina)
                if not filas:
                    sin_tabla.append(codigo)
                    logger.warning("%s: sin tabla de constituyentes", codigo)
                    continue

                index_id, pais = self._indice(session, codigo)
                if index_id is None:
                    logger.warning("%s: no esta en equity.market_index", codigo)
                    continue

                exchange_id = self._bolsa(session, mic)

                for ticker_bruto, nombre in filas:
                    ticker = self._normalizar_ticker(ticker_bruto, sufijo)
                    if not ticker:
                        continue

                    company_id, es_nueva = self._asegurar_empresa(
                        session, ticker, nombre, pais, exchange_id
                    )
                    nuevas += int(es_nueva)
                    vinculos += self._vincular(
                        session, index_id, company_id, src_id
                    )

                session.commit()
                procesados += 1
                logger.info(
                    "%s: %d constituyentes procesados", codigo, len(filas)
                )

            self._finish_run(
                run_id,
                "success" if not sin_tabla else "partial",
                fetched=vinculos,
                inserted=nuevas,
                errors=len(sin_tabla),
            )
            logger.info(
                "Indices: %d procesados, %d empresas nuevas, %d vinculos",
                procesados,
                nuevas,
                vinculos,
            )
        except Exception as e:
            self._finish_run(run_id, "failed", error_log={"msg": str(e)})
            logger.error("Constituyentes internacionales fallo: %s", e)
            raise
        finally:
            session.close()

        if con_precios and nuevas:
            self._descargar_precios_nuevas()

        return {
            "indices": procesados,
            "empresas_nuevas": nuevas,
            "vinculos": vinculos,
            "sin_tabla": sin_tabla,
        }

    # ── Internos ─────────────────────────────────

    def _extraer(self, pagina: str) -> list[tuple[str, str]]:
        """Sacar (ticker, nombre) de la pagina de un indice.

        Se elige la tabla mas larga que tenga a la vez una columna de
        simbolo y una de nombre: las paginas traen veinte tablas y la
        de constituyentes no esta siempre en la misma posicion.
        """
        self._rate_limit()
        try:
            resp = self._session.get(
                WIKI + pagina,
                headers={
                    "User-Agent": "stonks/0.4 (base de datos privada)",
                    "Accept": "text/html",
                },
                timeout=60,
            )
            resp.raise_for_status()
            tablas = pd.read_html(io.StringIO(resp.text))
        except (requests.RequestException, ValueError) as e:
            logger.warning("Wikipedia %s: %s", pagina, e)
            return []

        mejor: list[tuple[str, str]] = []
        for tabla in tablas:
            columnas = {
                self._limpiar_columna(c): c for c in tabla.columns
            }
            col_ticker = self._buscar(columnas, COLUMNAS_TICKER)
            col_nombre = self._buscar(columnas, COLUMNAS_NOMBRE)
            if col_ticker is None or col_nombre is None:
                continue

            filas = []
            for _, fila in tabla.iterrows():
                ticker = str(fila[col_ticker]).strip()
                nombre = str(fila[col_nombre]).strip()
                if not ticker or ticker.lower() == "nan":
                    continue
                if not nombre or nombre.lower() == "nan":
                    nombre = ticker
                filas.append((ticker, nombre))

            if len(filas) > len(mejor):
                mejor = filas

        return mejor

    @staticmethod
    def _limpiar_columna(nombre) -> str:
        """Encabezado comparable: minusculas y sin notas al pie."""
        txt = str(nombre).lower()
        txt = re.sub(r"\[.*?\]", "", txt)
        return re.sub(r"[^a-z ]", " ", txt).strip()

    @staticmethod
    def _buscar(columnas: dict, candidatos: tuple) -> str | None:
        """Primera columna cuyo encabezado contiene un candidato."""
        for candidato in candidatos:
            for limpio, original in columnas.items():
                if candidato in limpio.split() or limpio == candidato:
                    return original
        # Segunda pasada, mas laxa (p.ej. "ticker symbol").
        for candidato in candidatos:
            for limpio, original in columnas.items():
                if candidato in limpio:
                    return original
        return None

    @staticmethod
    def _normalizar_ticker(bruto: str, sufijo: str) -> str | None:
        """Dejar el ticker en el formato que espera yfinance."""
        ticker = str(bruto).strip().upper()
        # Wikipedia mete notas al pie y prefijos de bolsa.
        ticker = re.sub(r"\[.*?\]", "", ticker)
        ticker = ticker.split(":")[-1].strip()
        ticker = ticker.replace(" ", "")
        if not ticker or not PATRON_TICKER.match(ticker):
            return None
        # Si ya trae sufijo de mercado, se respeta.
        if sufijo and "." not in ticker:
            ticker += sufijo
        return ticker[:20]

    @staticmethod
    def _indice(session, codigo: str) -> tuple[int | None, str | None]:
        """id y pais del indice en equity.market_index."""
        fila = session.execute(
            text(
                "SELECT id, country_code FROM equity.market_index "
                "WHERE code = :c"
            ),
            {"c": codigo},
        ).first()
        return (fila[0], fila[1]) if fila else (None, None)

    @staticmethod
    def _bolsa(session, mic: str | None) -> int | None:
        """id de ref.exchange a partir del MIC."""
        if not mic:
            return None
        return session.execute(
            text("SELECT id FROM ref.exchange WHERE mic = :m"), {"m": mic}
        ).scalar()

    @staticmethod
    def _asegurar_empresa(
        session,
        ticker: str,
        nombre: str,
        pais: str | None,
        exchange_id: int | None,
    ) -> tuple[int, bool]:
        """Devolver (company_id, es_nueva) creando la empresa si falta.

        La clave natural de `equity.company` es (ticker, exchange_id),
        asi que se busca por ambos: el mismo ticker en dos mercados son
        dos filas distintas, que es justo lo que representa.
        """
        fila = session.execute(
            text(
                "SELECT id FROM equity.company "
                "WHERE ticker = :t AND exchange_id IS NOT DISTINCT FROM :e"
            ),
            {"t": ticker, "e": exchange_id},
        ).first()
        if fila:
            return fila[0], False

        nuevo = session.execute(
            text(
                "INSERT INTO equity.company "
                "(name, ticker, country_code, exchange_id, is_active, "
                " last_updated) "
                "VALUES (:n, :t, :p, :e, true, now()) "
                "RETURNING id"
            ),
            {"n": nombre[:500], "t": ticker, "p": pais, "e": exchange_id},
        ).scalar()
        return nuevo, True

    @staticmethod
    def _vincular(
        session, index_id: int, company_id: int, src_id: int
    ) -> int:
        """Registrar la pertenencia al indice. 1 si es nueva."""
        resultado = session.execute(
            text(
                "INSERT INTO equity.index_constituent_current "
                "(index_id, company_id, as_of_date, source_id) "
                "VALUES (:i, :c, CURRENT_DATE, :s) "
                "ON CONFLICT (index_id, company_id) DO UPDATE "
                "SET as_of_date = CURRENT_DATE"
            ),
            {"i": index_id, "c": company_id, "s": src_id},
        )
        return resultado.rowcount or 0

    @staticmethod
    def _descargar_precios_nuevas() -> None:
        """Bajar el historico de las empresas sin ningun precio."""
        from stonks.fetchers.yfinance_ import YFinanceFetcher

        session = get_session()
        try:
            faltan = session.execute(
                text(
                    "SELECT c.id, c.ticker FROM equity.company c "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM equity.price_daily p "
                    "  WHERE p.company_id = c.id"
                    ")"
                )
            ).fetchall()
        finally:
            session.close()

        yf = YFinanceFetcher()
        con_datos = 0
        for company_id, ticker in faltan:
            resultado = yf.fetch_prices(
                ticker, period="max", company_id=company_id
            )
            if resultado.get("inserted", 0) > 0:
                con_datos += 1
        logger.info(
            "Precios internacionales: %d/%d con datos",
            con_datos,
            len(faltan),
        )

    @staticmethod
    def _ensure_source(session) -> int:
        """Registrar la fuente si falta."""
        src = (
            session.query(DataSource)
            .filter_by(name="wikipedia_indices")
            .first()
        )
        if not src:
            src = DataSource(
                name="wikipedia_indices",
                display_name="Wikipedia (constituyentes de indices)",
                base_url=WIKI,
                rate_limit_per_second=0.7,
                is_enabled=True,
                notes=(
                    "Listas de constituyentes de los indices mundiales. "
                    "Unica fuente gratuita con cobertura fuera de EE.UU."
                ),
            )
            session.add(src)
            session.commit()
        return src.id
