"""Genera docs/DATA_DICTIONARY.md introspeccionando la BD real.

Recorre PostgreSQL (pg_catalog) para listar, por esquema, cada tabla /
vista / materializada con sus columnas, tipos, claves (PK/FK) y nº de
filas. Las descripciones de tabla salen de los docstrings de los modelos
SQLAlchemy. Regenerable: `python scripts/gen_data_dictionary.py`.
"""

from pathlib import Path

from sqlalchemy import text

import stonks.models  # noqa: F401  (registra los modelos)
from stonks.db import Base, engine

# Grupos de esquemas (orden y título del documento)
GROUPS = [
    ("Referencia y metadatos", ["ref", "meta"]),
    (
        "Renta variable y mercados financieros",
        ["equity", "fi", "commodity", "forex", "crypto", "fund", "alt"],
    ),
    ("Economía mundial", ["macro", "trade", "energy", "agri", "country"]),
    ("Derivados", ["deriv"]),
    ("Medallion — aterrizaje y analítica", ["bronze", "gold"]),
]

SCHEMA_DESC = {
    "ref": "Datos de referencia: países, divisas, bolsas, sectores GICS.",
    "meta": "Metadatos y auditoría: fuentes, ejecuciones, calidad.",
    "macro": "Economía mundial como series país × indicador × fecha.",
    "equity": "Renta variable: empresas, precios, fundamentales y 360°.",
    "fi": "Renta fija: bonos, ratings, curvas de tipos.",
    "commodity": "Materias primas y sus precios.",
    "forex": "Divisas y tipos de cambio.",
    "crypto": "Criptomonedas.",
    "fund": "ETFs y fondos.",
    "alt": "Datos alternativos: sentimiento, vivienda.",
    "trade": "Comercio internacional bilateral (país × socio).",
    "energy": "Balance energético por país, fuente y flujo.",
    "agri": "Producción agrícola por país, cultivo/ganado y elemento.",
    "country": "Perfiles de país: demografía, impuestos.",
    "deriv": "Derivados: snapshots de cadenas de opciones.",
    "bronze": "Aterrizaje crudo (JSONB) de las fuentes nuevas.",
    "gold": "Capa analítica point-in-time: hechos, dimensiones y marts.",
}

# Descripción curada de vistas/materializadas de gold (no son modelos ORM)
VIEW_DESC = {
    "mart_country_year": "Panel ancho país × año: macro + energía + "
    "comercio + emisiones (tabla analítica principal).",
    "mart_trade_matrix": "Matriz de comercio bilateral reporter × "
    "partner × año (exportaciones e importaciones).",
    "mart_benchmark_returns": "Retorno diario del pool S&P 500 "
    "equiponderado (survivorship-free) vs SPY.",
    "mart_pool_membership": "Universo S&P 500 point-in-time expandido a "
    "días de cotización.",
    "dim_indicator": "Catálogo autodocumentado de indicadores macro "
    "(código, fuente, cobertura, rango).",
}

KIND = {"r": "tabla", "m": "materializada", "v": "vista", "p": "tabla"}

# Explicación NO técnica de cada tabla (en lenguaje llano). Si no está
# aquí, se usa el docstring del modelo.
TABLE_DESC = {
    "ref.country": "Lista de países del mundo, con su código ISO.",
    "ref.currency": "Lista de monedas (euro, dólar...).",
    "ref.exchange": "Bolsas de valores (Nasdaq, NYSE...).",
    "ref.sector": "Sectores económicos GICS (Tecnología, Salud...).",
    "meta.data_source": "Las fuentes de donde sacamos los datos (IMF, "
    "yfinance, SEC...).",
    "meta.fetch_run": "Un registro por cada descarga hecha: cuándo, qué "
    "fuente, cuántos datos y si hubo errores. Es el 'diario' de descargas.",
    "meta.transform_run": "Un registro por cada vez que transformamos "
    "datos crudos en datos limpios. El 'diario' de transformaciones.",
    "meta.data_quality": "Nota de calidad por dominio: cuántos países "
    "cubrimos y cómo de reciente es el dato.",
    "macro.indicator": "El catálogo de indicadores económicos que "
    "seguimos (PIB, inflación, paro...). Cada fila es un indicador.",
    "macro.indicator_source": "Cómo se llama cada indicador en cada "
    "fuente (el mismo 'PIB' tiene códigos distintos en IMF y World Bank).",
    "macro.series": "Una serie = un indicador para un país concreto "
    "(p.ej. 'inflación de España'). Agrupa sus valores en el tiempo.",
    "macro.data_point": "El dato en sí: el valor de una serie en una "
    "fecha (p.ej. inflación de España en 2022 = 8,3%).",
    "equity.company": "Cada empresa cotizada que seguimos.",
    "equity.price_daily": "El precio de cierre diario de cada acción "
    "(y máximo, mínimo, volumen...).",
    "equity.income_statement": "Cuenta de resultados anual (ingresos, "
    "beneficio...) de cada empresa.",
    "equity.balance_sheet": "Balance anual (activos, deudas, patrimonio) "
    "de cada empresa.",
    "equity.cash_flow": "Flujos de caja anuales de cada empresa.",
    "equity.dividend": "Dividendos pagados por cada acción.",
    "equity.split": "Splits (desdoblamientos) de acciones.",
    "equity.holder": "Quién posee cada empresa: grandes fondos e "
    "instituciones, con su porcentaje.",
    "equity.insider_transaction": "Compras y ventas de acciones por parte "
    "de directivos e insiders de la empresa.",
    "equity.upgrade_downgrade": "Cambios de recomendación y precio "
    "objetivo que hacen los analistas (comprar/vender).",
    "equity.recommendation_trend": "Resumen de cuántos analistas "
    "recomiendan comprar, mantener o vender.",
    "equity.shares_history": "Número de acciones en circulación de la "
    "empresa a lo largo del tiempo.",
    "equity.earnings_date": "Fechas de presentación de resultados, con lo "
    "esperado vs lo reportado.",
    "equity.analyst_estimate": "Previsiones de los analistas sobre "
    "beneficios e ingresos futuros.",
    "equity.earnings_revision": "Cómo van cambiando esas previsiones (si "
    "los analistas revisan al alza o a la baja).",
    "equity.market_index": "Índices bursátiles (S&P 500, DAX...).",
    "equity.index_price": "Valor de cierre diario de cada índice.",
    "equity.index_constituent_current": "Qué empresas componen hoy cada "
    "índice.",
    "equity.ratios_mv": "Ratios de valoración calculados (PER, ROE...) — "
    "foto actual.",
    "fi.bond": "Bonos (sobre todo deuda pública de EE.UU.).",
    "fi.bond_issuer": "Emisores de bonos (países).",
    "fi.credit_rating": "Ratings de crédito (calificaciones de solvencia).",
    "fi.yield_curve": "Curvas de tipos de interés (rendimiento de la deuda "
    "por plazo).",
    "commodity.commodity": "Materias primas (oro, petróleo...).",
    "commodity.price_daily": "Precio diario de cada materia prima.",
    "forex.currency_pair": "Pares de divisas (EUR/USD...).",
    "forex.rate_daily": "Tipo de cambio diario de cada par.",
    "crypto.coin": "Criptomonedas (Bitcoin, Ethereum...).",
    "crypto.price_daily": "Precio diario de cada cripto.",
    "fund.fund": "ETFs y fondos de inversión.",
    "fund.nav_daily": "Valor liquidativo (NAV) diario de cada fondo.",
    "trade.flow": "Comercio entre dos países: cuánto exporta/importa un "
    "país a otro cada año.",
    "energy.balance": "Energía por país y fuente (carbón, gas, solar...): "
    "cuánto se produce y consume.",
    "agri.production": "Producción agrícola: cuánto trigo, maíz, carne... "
    "produce cada país cada año.",
    "country.profile": "Perfil de cada país (datos generales).",
    "country.demographics": "Datos demográficos por país.",
    "deriv.option_snapshot": "Foto diaria de las opciones (contratos de "
    "compra/venta) de las empresas más líquidas.",
    "bronze.api_response": "La respuesta cruda de una API macro, guardada "
    "tal cual por si hay que reprocesarla.",
    "bronze.sec_companyfacts": "El JSON crudo con todos los datos "
    "financieros que publica la SEC de cada empresa.",
    "bronze.yf_profile": "El perfil completo de una empresa tal cual lo "
    "devuelve yfinance.",
    "gold.dim_company": "Ficha resumida de cada empresa para análisis "
    "(con su sector ya incorporado).",
    "gold.dim_country": "Ficha de cada país (región, grupo de renta).",
    "gold.dim_date": "Calendario: una fila por día, con año, trimestre...",
    "gold.index_membership": "Qué empresas estaban en el S&P 500 en cada "
    "momento del pasado (para análisis sin 'trampa').",
    "gold.fact_fundamentals_pit": "Todos los datos financieros de las "
    "empresas US con la fecha en que se publicaron (para saber qué se "
    "sabía en cada momento). Es la tabla más grande.",
    "gold.fact_factor_scores": "Puntuaciones de factores de inversión "
    "(Value/Quality/Momentum) de cada empresa, normalizadas por sector.",
    "gold.mart_country_year": "La tabla estrella: una fila por país y año "
    "con TODO junto (PIB, inflación, paro, CO2, energía, comercio...).",
    "gold.mart_trade_matrix": "Matriz de comercio: exportaciones e "
    "importaciones entre cada par de países.",
}

# Explicación de columnas comunes (se aplican en todas las tablas).
COMMON_COLS = {
    "id": "Identificador único de la fila.",
    "company_id": "Empresa a la que pertenece.",
    "country_code": "País (código ISO-3, p.ej. ESP).",
    "reporter_code": "País que declara (exporta/importa).",
    "partner_code": "País socio comercial.",
    "source_id": "Fuente de la que procede el dato.",
    "fetch_run_id": "Descarga que trajo el dato (auditoría).",
    "date": "Fecha del dato.",
    "period": "Año del dato.",
    "year": "Año.",
    "snapshot_date": "Día de la foto (los datos se acumulan por día).",
    "fetched_at": "Cuándo se descargó.",
    "ingested_at": "Cuándo se guardó el dato crudo.",
    "assessed_at": "Cuándo se evaluó.",
    "last_updated": "Última actualización.",
    "as_of_date": "Fecha de referencia del cálculo.",
    "currency_code": "Moneda del importe.",
    "ticker": "Símbolo bursátil (p.ej. AAPL).",
    "name": "Nombre.",
    "value": "Valor del dato.",
    "unit": "Unidad de medida.",
    "payload": "Respuesta cruda de la API (JSON), tal cual llegó.",
    "indicator_id": "Indicador al que pertenece.",
    "series_id": "Serie temporal a la que pertenece.",
    "index_id": "Índice de mercado.",
    "sector_id": "Sector GICS.",
    "exchange_id": "Bolsa de valores.",
    "fiscal_year": "Año fiscal del periodo.",
    "fiscal_quarter": "Trimestre fiscal (vacío = dato anual).",
    "status": "Estado (running / success / failed).",
    "category": "Categoría o dominio.",
    "subcategory": "Subcategoría.",
    "frequency": "Frecuencia (anual, mensual, diario...).",
    "description": "Descripción libre.",
    "code": "Código identificador.",
    "period_end_date": "Fecha de cierre del periodo contable.",
    "filed_date": "Fecha en que se publicó/presentó el dato.",
    "publish_date": "Fecha de publicación.",
    "metric": "Nombre de la métrica (concepto financiero).",
    "open": "Precio de apertura.",
    "high": "Precio máximo del día.",
    "low": "Precio mínimo del día.",
    "close": "Precio de cierre.",
    "adj_close": "Precio de cierre ajustado (dividendos/splits).",
    "volume": "Volumen negociado.",
    "market_cap_usd": "Capitalización bursátil en dólares.",
    # Perfil de empresa
    "isin": "Código ISIN (identificador internacional del valor).",
    "shares_outstanding": "Acciones en circulación.",
    "ipo_date": "Fecha de salida a bolsa.",
    "delisted_date": "Fecha en que dejó de cotizar.",
    "is_active": "Si sigue cotizando (no deslistada).",
    "website": "Web de la empresa.",
    "employees": "Número de empleados.",
    # Cuenta de resultados
    "revenue": "Ingresos totales (ventas).",
    "cost_of_revenue": "Coste de las ventas.",
    "gross_profit": "Beneficio bruto.",
    "operating_expenses": "Gastos operativos.",
    "operating_income": "Beneficio operativo.",
    "interest_expense": "Gastos financieros (intereses).",
    "pretax_income": "Beneficio antes de impuestos.",
    "income_tax": "Impuestos sobre beneficios.",
    "net_income": "Beneficio neto (lo que gana al final).",
    "eps_basic": "Beneficio por acción (básico).",
    "eps_diluted": "Beneficio por acción (diluido).",
    "shares_basic": "Nº de acciones (básico).",
    "shares_diluted": "Nº de acciones (diluido).",
    "ebitda": "EBITDA (beneficio antes de intereses, impuestos y "
    "amortizaciones).",
    # Balance
    "cash_and_equivalents": "Efectivo y equivalentes.",
    "short_term_investments": "Inversiones a corto plazo.",
    "total_current_assets": "Activo corriente total.",
    "property_plant_equipment": "Inmovilizado material (fábricas, "
    "equipos...).",
    "goodwill": "Fondo de comercio.",
    "intangible_assets": "Activos intangibles.",
    "total_assets": "Activos totales.",
    "accounts_payable": "Cuentas a pagar (a proveedores).",
    "short_term_debt": "Deuda a corto plazo.",
    "total_current_liabilities": "Pasivo corriente total.",
    "long_term_debt": "Deuda a largo plazo.",
    "total_liabilities": "Pasivos totales (todo lo que debe).",
    "total_stockholders_equity": "Patrimonio de los accionistas.",
    "retained_earnings": "Beneficios retenidos (no repartidos).",
    "total_equity": "Patrimonio neto total.",
    # Flujos de caja
    "operating_cash_flow": "Flujo de caja de las operaciones.",
    "capital_expenditure": "Inversión en activos (capex).",
    "free_cash_flow": "Flujo de caja libre.",
    "dividends_paid": "Dividendos pagados.",
    "share_buyback": "Recompra de acciones propias.",
    "debt_issued": "Deuda emitida.",
    "debt_repaid": "Deuda devuelta.",
    "investing_cash_flow": "Flujo de caja de inversión.",
    "financing_cash_flow": "Flujo de caja de financiación.",
    "net_change_cash": "Variación neta de efectivo.",
}

# Explicación de columnas específicas (clave: 'esquema.tabla.columna').
COL_DESC = {
    "macro.data_point.value": "El valor del indicador en esa fecha.",
    "macro.series.last_value": "Último valor conocido de la serie.",
    "macro.series.point_count": "Cuántos datos tiene la serie.",
    "macro.indicator.unit": "En qué se mide (%, USD, personas...).",
    "trade.flow.flow": "Sentido: X = exportación, M = importación.",
    "trade.flow.value_usd_k": "Valor comerciado en miles de dólares.",
    "trade.flow.product_code": "Producto (Total = todos los productos).",
    "energy.balance.product_code": "Fuente de energía (coal, gas, solar...).",
    "energy.balance.flow": "consumption / production / electricity.",
    "agri.production.item_code": "Código del cultivo o ganado.",
    "agri.production.item_name": "Nombre del cultivo/ganado (Wheat...).",
    "agri.production.element": "Qué se mide (producción, rendimiento...).",
    "deriv.option_snapshot.expiry": "Fecha de vencimiento del contrato.",
    "deriv.option_snapshot.option_type": "C = call (compra), P = put (venta).",
    "deriv.option_snapshot.strike": "Precio de ejercicio del contrato.",
    "deriv.option_snapshot.implied_vol": "Volatilidad implícita.",
    "deriv.option_snapshot.open_interest": "Contratos abiertos vivos.",
    "equity.company.is_active": "Si la empresa sigue cotizando (no "
    "deslistada).",
    "equity.company.delisted_date": "Fecha en que dejó de cotizar.",
    "equity.holder.holder_type": "Tipo: institutional o mutualfund.",
    "equity.holder.pct_held": "% de la empresa que posee.",
    "equity.holder.shares": "Nº de acciones que posee.",
    "equity.insider_transaction.insider": "Nombre del directivo/insider.",
    "equity.insider_transaction.transaction": "Compra o venta.",
    "equity.upgrade_downgrade.firm": "Casa de análisis (Goldman...).",
    "equity.upgrade_downgrade.to_grade": "Nueva recomendación.",
    "equity.upgrade_downgrade.price_target": "Precio objetivo fijado.",
    "equity.earnings_date.eps_estimate": "Beneficio por acción esperado.",
    "equity.earnings_date.reported_eps": "Beneficio por acción real.",
    "gold.fact_fundamentals_pit.metric": "Concepto financiero (revenue, "
    "net_income o el código XBRL completo).",
    "gold.fact_fundamentals_pit.value": "Importe del concepto.",
    "gold.fact_factor_scores.factor": "value, quality o momentum.",
    "gold.fact_factor_scores.z_sector_neutral": "Puntuación normalizada "
    "dentro de su sector (para comparar manzanas con manzanas).",
    "gold.index_membership.start_date": "Cuándo entró en el índice.",
    "gold.index_membership.end_date": "Cuándo salió (vacío = sigue dentro).",
    # Panel país-año (la tabla estrella)
    "gold.mart_country_year.gdp_usd_bn": "PIB en miles de millones de USD.",
    "gold.mart_country_year.gdp_per_capita_usd": "PIB por habitante (USD).",
    "gold.mart_country_year.gdp_growth_pct": "Crecimiento del PIB (%).",
    "gold.mart_country_year.gdp_ppp_bn": "PIB en paridad de poder "
    "adquisitivo (miles de millones).",
    "gold.mart_country_year.gdp_ppp_per_capita": "PIB PPA por habitante.",
    "gold.mart_country_year.share_world_gdp_ppp_pct": "% que representa "
    "del PIB mundial (PPA).",
    "gold.mart_country_year.inflation_pct": "Inflación anual (%).",
    "gold.mart_country_year.unemployment_pct": "Tasa de paro (%).",
    "gold.mart_country_year.population_mn": "Población (millones).",
    "gold.mart_country_year.gov_debt_pct_gdp": "Deuda pública (% del PIB).",
    "gold.mart_country_year.gov_balance_pct_gdp": "Saldo público: déficit "
    "o superávit (% del PIB).",
    "gold.mart_country_year.gov_revenue_pct_gdp": "Ingresos del Estado "
    "(% del PIB).",
    "gold.mart_country_year.gov_expenditure_pct_gdp": "Gasto del Estado "
    "(% del PIB).",
    "gold.mart_country_year.savings_pct_gdp": "Ahorro nacional (% del PIB).",
    "gold.mart_country_year.investment_pct_gdp": "Inversión (% del PIB).",
    "gold.mart_country_year.current_account_pct_gdp": "Cuenta corriente "
    "(% del PIB): lo que el país presta o toma prestado al exterior.",
    "gold.mart_country_year.co2_mt": "Emisiones de CO2 (millones de "
    "toneladas).",
    "gold.mart_country_year.co2_per_capita_t": "CO2 por habitante "
    "(toneladas).",
    "gold.mart_country_year.co2_share_global_pct": "% del CO2 mundial.",
    "gold.mart_country_year.ghg_mt": "Gases de efecto invernadero totales "
    "(Mt CO2 eq.).",
    "gold.mart_country_year.primary_energy_twh": "Energía primaria "
    "consumida (TWh).",
    "gold.mart_country_year.electricity_twh": "Electricidad generada (TWh).",
    "gold.mart_country_year.renewables_elec_twh": "Electricidad renovable "
    "(TWh).",
    "gold.mart_country_year.renewables_share_elec_pct": "% de la "
    "electricidad que es renovable.",
    "gold.mart_country_year.exports_usd_bn": "Exportaciones de bienes "
    "(miles de millones USD).",
    "gold.mart_country_year.imports_usd_bn": "Importaciones de bienes "
    "(miles de millones USD).",
    "gold.mart_country_year.trade_balance_usd_bn": "Balanza comercial "
    "(exportaciones − importaciones).",
    "gold.mart_trade_matrix.exports_usd_k": "Exportaciones del reporter al "
    "socio (miles de USD).",
    "gold.mart_trade_matrix.imports_usd_k": "Importaciones del reporter "
    "desde el socio (miles de USD).",
}


def _table_docs() -> dict[tuple[str, str], str]:
    """(esquema, tabla) → docstring del modelo SQLAlchemy."""
    out: dict[tuple[str, str], str] = {}
    for mapper in Base.registry.mappers:
        t = mapper.local_table
        if t is None or t.schema is None:
            continue
        doc = (mapper.class_.__doc__ or "").strip().split("\n")[0]
        out[(t.schema, t.name)] = doc
    return out


def _relations(conn, schema: str):
    """Relaciones (tabla/vista/matview) de un esquema, con nº de filas."""
    sql = text(
        "SELECT c.relname, c.relkind, "
        "  CASE WHEN c.reltuples < 0 THEN 0 ELSE c.reltuples::bigint END "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = :s AND c.relkind IN ('r','m','v','p') "
        "ORDER BY c.relname"
    )
    return list(conn.execute(sql, {"s": schema}))


def _columns(conn, schema: str, table: str):
    """Columnas (nombre, tipo, nullable) de una relación."""
    sql = text(
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod), "
        "  NOT a.attnotnull "
        "FROM pg_attribute a "
        "JOIN pg_class c ON c.oid = a.attrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = :s AND c.relname = :t "
        "  AND a.attnum > 0 AND NOT a.attisdropped "
        "ORDER BY a.attnum"
    )
    return list(conn.execute(sql, {"s": schema, "t": table}))


def _keys(conn, schema: str, table: str):
    """Devuelve (set de columnas PK, dict col→destino FK)."""
    p = {"s": schema, "t": table}
    pk = {
        r[0]
        for r in conn.execute(
            text(
                "SELECT a.attname FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "JOIN pg_attribute a ON a.attrelid = i.indrelid "
                "  AND a.attnum = ANY(i.indkey) "
                "WHERE n.nspname = :s AND c.relname = :t "
                "  AND i.indisprimary"
            ),
            p,
        )
    }
    fk = {}
    for col, fs, ft, fc in conn.execute(
        text(
            "SELECT att.attname, ns2.nspname, cl2.relname, att2.attname "
            "FROM pg_constraint con "
            "JOIN pg_class cl ON cl.oid = con.conrelid "
            "JOIN pg_namespace ns ON ns.oid = cl.relnamespace "
            "JOIN pg_attribute att ON att.attrelid = con.conrelid "
            "  AND att.attnum = ANY(con.conkey) "
            "JOIN pg_class cl2 ON cl2.oid = con.confrelid "
            "JOIN pg_namespace ns2 ON ns2.oid = cl2.relnamespace "
            "JOIN pg_attribute att2 ON att2.attrelid = con.confrelid "
            "  AND att2.attnum = ANY(con.confkey) "
            "WHERE ns.nspname = :s AND cl.relname = :t "
            "  AND con.contype = 'f'"
        ),
        p,
    ):
        fk[col] = f"{fs}.{ft}.{fc}"
    return pk, fk


def generate() -> str:
    docs = _table_docs()
    out = [
        "# Diccionario de datos — stonks_db",
        "",
        "> Generado automáticamente desde el esquema real "
        "(`python scripts/gen_data_dictionary.py`).",
        "> No editar a mano. Para el diseño ver "
        "[ARCHITECTURE.md](ARCHITECTURE.md) y "
        "[SCHEMA_RELATIONS.md](SCHEMA_RELATIONS.md).",
        "",
        "Este documento explica **en lenguaje llano qué es cada tabla y "
        "cada columna** de la base de datos. Está agrupado por temas.",
        "",
        "Cómo leer cada tabla:",
        "- **Columna**: el nombre técnico del campo.",
        "- **Qué es**: explicación sencilla de lo que guarda.",
        "- **Tipo**: formato del dato (número, texto, fecha...).",
        "- **Nulo**: si puede estar vacío.",
        "- **Clave**: `PK` = identifica la fila; `FK →` = enlaza con otra "
        "tabla.",
        "",
    ]
    with engine.connect() as conn:
        for grupo, schemas in GROUPS:
            out.append(f"## {grupo}\n")
            for schema in schemas:
                rels = _relations(conn, schema)
                if not rels:
                    continue
                out.append(f"### Esquema `{schema}`")
                out.append(f"_{SCHEMA_DESC.get(schema, '')}_\n")
                for name, kind, nrows in rels:
                    # Descripción llana: TABLE_DESC > docstring > vista
                    desc = (
                        TABLE_DESC.get(f"{schema}.{name}")
                        or docs.get((schema, name))
                        or VIEW_DESC.get(name, "")
                    )
                    etiqueta = KIND.get(kind, kind)
                    out.append(
                        f"#### `{schema}.{name}` "
                        f"· {etiqueta} · ~{nrows:,} filas"
                    )
                    if desc:
                        out.append(f"{desc}\n")
                    pk, fk = _keys(conn, schema, name)
                    out.append("| Columna | Qué es | Tipo | Nulo | Clave |")
                    out.append("|---|---|---|---|---|")
                    for col, tipo, nullable in _columns(conn, schema, name):
                        clave = ""
                        if col in pk:
                            clave = "PK"
                        elif col in fk:
                            clave = f"FK → {fk[col]}"
                        nulo = "sí" if nullable else "no"
                        que = COL_DESC.get(
                            f"{schema}.{name}.{col}"
                        ) or COMMON_COLS.get(col, "")
                        out.append(
                            f"| `{col}` | {que} | {tipo} | {nulo} | {clave} |"
                        )
                    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    destino = Path(__file__).resolve().parent.parent / "docs"
    destino.mkdir(exist_ok=True)
    (destino / "DATA_DICTIONARY.md").write_text(generate(), encoding="utf-8")
    print("Escrito docs/DATA_DICTIONARY.md")
