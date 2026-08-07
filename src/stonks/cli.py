"""CLI principal de Stonks."""

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="stonks",
    help="Base de datos global de inversión",
    no_args_is_help=True,
)
macro_app = typer.Typer(
    help="Datos macroeconómicos",
    no_args_is_help=True,
)
equity_app = typer.Typer(
    help="Renta variable",
    no_args_is_help=True,
)
fi_app = typer.Typer(
    help="Renta fija",
    no_args_is_help=True,
)
commodity_app = typer.Typer(
    help="Materias primas",
    no_args_is_help=True,
)
forex_app = typer.Typer(
    help="Divisas / Forex",
    no_args_is_help=True,
)
crypto_app = typer.Typer(
    help="Criptomonedas",
    no_args_is_help=True,
)
fund_app = typer.Typer(
    help="ETFs y fondos",
    no_args_is_help=True,
)
country_app = typer.Typer(
    help="Perfiles de país",
    no_args_is_help=True,
)
alt_app = typer.Typer(
    help="Datos alternativos (VIX, sentimiento)",
    no_args_is_help=True,
)
index_app = typer.Typer(
    help="Índices de mercado",
    no_args_is_help=True,
)
deriv_app = typer.Typer(
    help="Derivados (volatilidad, futuros)",
    no_args_is_help=True,
)
intraday_app = typer.Typer(
    help="Datos intraday (1m/5m/1h)",
    no_args_is_help=True,
)
realestate_app = typer.Typer(
    help="Inmobiliario (indices de precio de vivienda)",
    no_args_is_help=True,
)
calendar_app = typer.Typer(
    help="Calendario economico (publicaciones macro)",
    no_args_is_help=True,
)
ref_app = typer.Typer(
    help="Datos de referencia (LEI, areas, catalogos)",
    no_args_is_help=True,
)
app.add_typer(macro_app, name="macro")
app.add_typer(equity_app, name="equity")
app.add_typer(fi_app, name="fi")
app.add_typer(commodity_app, name="commodity")
app.add_typer(forex_app, name="forex")
app.add_typer(crypto_app, name="crypto")
app.add_typer(fund_app, name="fund")
app.add_typer(country_app, name="country")
app.add_typer(alt_app, name="alt")
app.add_typer(index_app, name="index")
app.add_typer(deriv_app, name="deriv")
app.add_typer(intraday_app, name="intraday")
app.add_typer(realestate_app, name="realestate")
app.add_typer(calendar_app, name="calendar")
app.add_typer(ref_app, name="ref")

console = Console()


# ── Comandos globales ────────────────────────────


@app.command()
def init(
    drop: bool = typer.Option(
        False,
        "--drop",
        help="Borrar todo y recrear",
    ),
) -> None:
    """Inicializar BD: esquemas, tablas, datos de
    referencia."""
    from stonks.db import drop_db, init_db
    from stonks.logger import setup_logger

    logger = setup_logger("stonks.cli")

    if drop:
        console.print("[yellow]Borrando tablas...[/yellow]")
        drop_db()

    console.print("Creando esquemas y tablas...")
    init_db()
    logger.info("Tablas creadas")

    # Seed datos de referencia
    console.print("Cargando datos de referencia...")
    from stonks.seed.reference import seed_all

    results = seed_all()
    for label, n in results.items():
        console.print(f"  {label}: {n}")

    console.print("[green]✓ Base de datos inicializada[/green]")


@app.command()
def world(
    country: str = typer.Argument(
        ..., help="Código ISO3 del país (p.ej. ESP, USA, CHN)"
    ),
    years: int = typer.Option(6, "-n", help="Número de años a mostrar"),
) -> None:
    """Panel de economía mundial de un país (gold.mart_country_year)."""
    from sqlalchemy import text

    from stonks.db import get_session

    session = get_session()
    rows = session.execute(
        text(
            "SELECT year, gdp_usd_bn, gdp_per_capita_usd, gdp_growth_pct, "
            "inflation_pct, unemployment_pct, gov_debt_pct_gdp, co2_mt, "
            "exports_usd_bn, is_forecast FROM gold.mart_country_year "
            "WHERE country_code = :c "
            "  AND year <= extract(year FROM now()) "
            "ORDER BY year DESC LIMIT :n"
        ),
        {"c": country.upper(), "n": years},
    ).fetchall()
    session.close()

    if not rows:
        console.print(f"[yellow]Sin datos para {country.upper()}[/yellow]")
        return

    table = Table(title=f"Economía — {country.upper()}")
    for col in (
        "Año",
        "PIB $bn",
        "PIB pc",
        "Crec%",
        "Infl%",
        "Paro%",
        "Deuda%",
        "CO2 Mt",
        "Export $bn",
    ):
        table.add_column(col, justify="right")

    def _fmt(v, dec: int) -> str:
        return "-" if v is None else f"{float(v):,.{dec}f}"

    for r in reversed(rows):
        # r: año, pib_bn, pib_pc, crec, infl, paro, deuda, co2, export,
        #    is_forecast
        # Los años proyectados llevan asterisco: son previsiones del
        # FMI y hasta ahora se mostraban igual que los datos reales.
        etiqueta = f"{int(r[0])}*" if r[9] else str(int(r[0]))
        table.add_row(
            etiqueta,
            _fmt(r[1], 0),
            _fmt(r[2], 0),
            _fmt(r[3], 1),
            _fmt(r[4], 1),
            _fmt(r[5], 1),
            _fmt(r[6], 1),
            _fmt(r[7], 0),
            _fmt(r[8], 0),
            style="dim" if r[9] else None,
        )
    console.print(table)
    if any(r[9] for r in rows):
        console.print(
            "  [dim]* proyección del FMI, no dato realizado[/dim]"
        )


@app.command()
def asset(
    ticker: str = typer.Argument(..., help="Ticker (p.ej. AAPL)"),
) -> None:
    """Ficha 360° de una empresa (profundidad de datos)."""
    from sqlalchemy import text

    from stonks.db import get_session

    session = get_session()
    tk = ticker.upper()
    row = session.execute(
        text(
            "SELECT c.id, c.name, c.country_code, c.market_cap_usd, "
            "s.name FROM equity.company c "
            "LEFT JOIN ref.sector s ON s.id = c.sector_id "
            "WHERE c.ticker = :t"
        ),
        {"t": tk},
    ).first()
    if not row:
        console.print(f"[yellow]Sin datos para {tk}[/yellow]")
        session.close()
        return
    cid = row[0]

    def _n(sql: str) -> int:
        return session.execute(text(sql), {"c": cid}).scalar() or 0

    console.print(f"[bold cyan]{tk}[/bold cyan] — {row[1]}")
    mc = f"{float(row[3]) / 1e9:,.1f} bn USD" if row[3] else "-"
    console.print(
        f"  Sector: {row[4] or '-'} · País: {row[2] or '-'} · Market cap: {mc}"
    )
    console.print(
        "  Profundidad de datos:\n"
        f"    · Fundamentales PIT: {_n('SELECT count(*) FROM gold.fact_fundamentals_pit WHERE company_id=:c'):,} hechos, "
        f"{_n('SELECT count(DISTINCT metric) FROM gold.fact_fundamentals_pit WHERE company_id=:c')} métricas\n"
        f"    · Precios diarios: {_n('SELECT count(*) FROM equity.price_daily WHERE company_id=:c'):,}\n"
        f"    · Accionistas: {_n('SELECT count(*) FROM equity.holder WHERE company_id=:c')}"
        f" · Insiders: {_n('SELECT count(*) FROM equity.insider_transaction WHERE company_id=:c')}\n"
        f"    · Upgrades/downgrades: {_n('SELECT count(*) FROM equity.upgrade_downgrade WHERE company_id=:c')}"
        f" · Opciones: {_n('SELECT count(*) FROM deriv.option_snapshot WHERE company_id=:c')}"
    )
    session.close()


@app.command()
def indicators(
    search: str = typer.Option(
        "", "-s", help="Filtrar por texto en código o nombre"
    ),
    category: str = typer.Option("", "-c", help="Filtrar por categoría"),
    limit: int = typer.Option(40, "-n", help="Máximo de filas"),
) -> None:
    """Catálogo de indicadores macro (gold.dim_indicator)."""
    from sqlalchemy import text

    from stonks.db import get_session

    where = ["n_points > 0"]
    params: dict = {"lim": limit}
    if search:
        where.append("(code ILIKE :s OR name ILIKE :s)")
        params["s"] = f"%{search}%"
    if category:
        where.append("category = :cat")
        params["cat"] = category
    sql = (
        "SELECT code, name, category, n_countries, first_date, last_date "
        "FROM gold.dim_indicator WHERE "
        + " AND ".join(where)
        + " ORDER BY n_points DESC LIMIT :lim"
    )
    session = get_session()
    rows = session.execute(text(sql), params).fetchall()
    session.close()

    table = Table(title="Catálogo de indicadores")
    for col in ("Código", "Nombre", "Categoría", "Países", "Desde", "Hasta"):
        table.add_column(col)
    for r in rows:
        table.add_row(
            r[0],
            (r[1] or "")[:45],
            r[2] or "-",
            str(r[3]),
            str(r[4].year if r[4] else "-"),
            str(r[5].year if r[5] else "-"),
        )
    console.print(table)


@app.command()
def audit(
    dominio: str = typer.Option(
        None, "--dominio", "-d", help="Filtrar por dominio"
    ),
    detalle: bool = typer.Option(
        False, "--detalle", help="Mostrar tambien los checks en verde"
    ),
    estricto: bool = typer.Option(
        False,
        "--estricto",
        help="Salir con codigo 1 si hay algun problema",
    ),
) -> None:
    """Auditoría completa de calidad de datos.

    Ejecuta los checks de cobertura e integridad y los de veracidad y
    completitud, y persiste el resultado en `meta.data_quality`. Antes
    solo corría tres de ellos y no guardaba nada.
    """
    from sqlalchemy import text

    from stonks.db import get_session
    from stonks.logger import setup_logger
    from stonks.quality import run_all_checks

    setup_logger("stonks.cli")

    console.print("Ejecutando checks de calidad...")
    run_all_checks()

    session = get_session()
    try:
        sql = (
            "SELECT domain, entity_type, entity_id, completeness_score, "
            "       source_count, freshness_days "
            "FROM meta.data_quality "
        )
        params: dict = {}
        if dominio:
            sql += "WHERE domain = :d "
            params["d"] = dominio
        sql += "ORDER BY completeness_score NULLS LAST, domain, entity_type"
        filas = session.execute(text(sql), params).fetchall()
    finally:
        session.close()

    problemas = [f for f in filas if (f[3] or 100) < 100]
    mostrar = filas if detalle else problemas

    if not mostrar:
        console.print("\n[green]✓ Sin problemas de calidad[/green]")
    else:
        tabla = Table(
            title=(
                "Calidad de datos"
                if detalle
                else "Problemas de calidad detectados"
            )
        )
        tabla.add_column("Dominio", style="cyan")
        tabla.add_column("Check")
        tabla.add_column("Entidad")
        tabla.add_column("Score", justify="right")
        tabla.add_column("N", justify="right")

        for dom, tipo, entidad, score, n, _dias in mostrar[:60]:
            color = "green" if (score or 0) >= 100 else "yellow"
            tabla.add_row(
                dom,
                tipo,
                (entidad or "")[:52],
                f"[{color}]{float(score):.0f}[/{color}]"
                if score is not None
                else "-",
                str(n) if n is not None else "-",
            )
        console.print(tabla)
        if len(mostrar) > 60:
            console.print(f"  ... y {len(mostrar) - 60} mas")

    console.print(
        f"\n{len(filas)} checks ejecutados, "
        f"[{'yellow' if problemas else 'green'}]{len(problemas)}"
        f"[/{'yellow' if problemas else 'green'}] con hallazgos"
    )

    if estricto and problemas:
        raise typer.Exit(code=1)


@app.command()
def certify(
    estricto: bool = typer.Option(
        False,
        "--estricto",
        help="Salir con código 1 si queda alguna tabla sin certificar",
    ),
    detalle: bool = typer.Option(
        False, "--detalle", help="Listar tabla por tabla"
    ),
) -> None:
    """Certificar cómo se ha verificado cada tabla de datos.

    Con datos de terceros no se puede garantizar que cada cifra sea
    cierta. Lo que sí se puede es que de cada tabla conste cómo se ha
    comprobado, o que conste que no se puede y por qué.
    """
    from stonks.certificacion import (
        CONTRASTADA,
        NO_VERIFICABLE,
        SIN_CERTIFICAR,
        certificar,
    )

    resultado = certificar()

    conteo: dict[str, int] = {}
    for r in resultado:
        conteo[r["estado"]] = conteo.get(r["estado"], 0) + 1

    colores = {
        CONTRASTADA: "green",
        NO_VERIFICABLE: "yellow",
        SIN_CERTIFICAR: "red",
    }
    resumen = Table(title="Certificación de stonks_db")
    resumen.add_column("Estado", style="cyan")
    resumen.add_column("Tablas", justify="right")
    for estado, n in sorted(conteo.items(), key=lambda x: -x[1]):
        color = colores.get(estado, "white")
        resumen.add_row(estado, f"[{color}]{n}[/{color}]")
    console.print(resumen)

    pendientes = [
        r for r in resultado if r["estado"] == SIN_CERTIFICAR
    ]
    if pendientes:
        console.print("\n[red]Sin certificar:[/red]")
        for r in pendientes:
            console.print(f"  {r['tabla']} ({r['filas']} filas)")
        console.print(
            "\nDeclara cada una en config/certificacion.yml, o mejor, "
            "añade un valor de referencia en tests/referencias.yml."
        )

    if detalle:
        tabla = Table(title="Detalle")
        tabla.add_column("Tabla", style="white")
        tabla.add_column("Estado", style="cyan")
        tabla.add_column("Filas", justify="right")
        for r in resultado:
            tabla.add_row(
                r["tabla"], r["estado"], f"{r['filas']:,}"
            )
        console.print(tabla)

    if estricto and pendientes:
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    """Mostrar estadísticas de la BD."""
    from sqlalchemy import text

    from stonks.db import get_session

    session = get_session()

    table = Table(title="Estado de Stonks DB")
    table.add_column("Dominio", style="cyan")
    table.add_column("Tabla", style="white")
    table.add_column("Registros", justify="right")

    # Contar registros en tablas principales
    queries = [
        ("ref", "Países", "SELECT COUNT(*) FROM ref.country"),
        ("ref", "Divisas", "SELECT COUNT(*) FROM ref.currency"),
        ("ref", "Bolsas", "SELECT COUNT(*) FROM ref.exchange"),
        ("ref", "Sectores", "SELECT COUNT(*) FROM ref.sector"),
        ("meta", "Fuentes", "SELECT COUNT(*) FROM meta.data_source"),
        ("meta", "Ejecuciones", "SELECT COUNT(*) FROM meta.fetch_run"),
        ("macro", "Indicadores", "SELECT COUNT(*) FROM macro.indicator"),
        ("macro", "Series", "SELECT COUNT(*) FROM macro.series"),
        ("macro", "Puntos datos", "SELECT COUNT(*) FROM macro.data_point"),
        ("equity", "Empresas", "SELECT COUNT(*) FROM equity.company"),
        (
            "equity",
            "Precios diarios",
            "SELECT COUNT(*) FROM equity.price_daily",
        ),
        (
            "equity",
            "Income statements",
            "SELECT COUNT(*) FROM equity.income_statement",
        ),
        (
            "equity",
            "Balance sheets",
            "SELECT COUNT(*) FROM equity.balance_sheet",
        ),
        ("equity", "Cash flows", "SELECT COUNT(*) FROM equity.cash_flow"),
        ("equity", "Dividendos", "SELECT COUNT(*) FROM equity.dividend"),
        ("fi", "Yield curves", "SELECT COUNT(*) FROM fi.yield_curve"),
        (
            "commodity",
            "Commodities",
            "SELECT COUNT(*) FROM commodity.commodity",
        ),
        ("commodity", "Precios", "SELECT COUNT(*) FROM commodity.price_daily"),
        ("forex", "Pares", "SELECT COUNT(*) FROM forex.currency_pair"),
        ("forex", "Tipos cambio", "SELECT COUNT(*) FROM forex.rate_daily"),
        ("crypto", "Coins", "SELECT COUNT(*) FROM crypto.coin"),
        ("crypto", "Precios", "SELECT COUNT(*) FROM crypto.price_daily"),
        ("fund", "ETFs/Fondos", "SELECT COUNT(*) FROM fund.fund"),
        ("fund", "NAV diario", "SELECT COUNT(*) FROM fund.nav_daily"),
        ("equity", "Índices", "SELECT COUNT(*) FROM equity.market_index"),
        (
            "equity",
            "Precios índices",
            "SELECT COUNT(*) FROM equity.index_price",
        ),
        ("country", "Perfiles", "SELECT COUNT(*) FROM country.profile"),
        ("country", "Demografía", "SELECT COUNT(*) FROM country.demographics"),
        ("alt", "Sentimiento", "SELECT COUNT(*) FROM alt.sentiment_value"),
    ]

    for domain, label, query in queries:
        try:
            result = session.execute(text(query)).scalar()
            table.add_row(domain, label, f"{result:,}")
        except Exception:
            table.add_row(domain, label, "-")

    session.close()
    console.print(table)


@app.command()
def update(
    cadence: str = typer.Option(
        "daily",
        "-c",
        "--cadence",
        help="Cadencia: daily | weekly | monthly | yearly | all",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Solo listar los pasos, sin ejecutarlos",
    ),
    no_build: bool = typer.Option(
        False,
        "--no-build",
        help="No reconstruir la capa gold al final",
    ),
) -> None:
    """Ejecutar el pipeline medallion de una cadencia."""
    from stonks.logger import setup_logger
    from stonks.pipeline import run_update

    setup_logger("stonks.cli")
    resumen = run_update(cadence, dry_run=dry_run, build=not no_build)

    table = Table(title=f"Pipeline ({cadence})")
    table.add_column("Paso", style="cyan")
    table.add_column("Estado")
    for paso, estado in resumen.items():
        color = "green" if estado in ("ok", "dry-run") else "red"
        table.add_row(paso, f"[{color}]{estado}[/{color}]")
    console.print(table)


@app.command()
def sources() -> None:
    """Mostrar fuentes de datos configuradas."""
    from stonks.db import get_session
    from stonks.models.meta import DataSource

    session = get_session()
    srcs = session.query(DataSource).order_by(DataSource.name).all()

    table = Table(title="Fuentes de Datos")
    table.add_column("Nombre", style="cyan")
    table.add_column("URL")
    table.add_column("Rate Limit")
    table.add_column("Activa", justify="center")

    for s in srcs:
        rl = (
            f"{s.rate_limit_per_second} req/s"
            if s.rate_limit_per_second
            else "-"
        )
        active = "[green]✓[/green]" if s.is_enabled else "[red]✗[/red]"
        table.add_row(
            s.name,
            s.base_url or "-",
            rl,
            active,
        )

    session.close()
    console.print(table)


# ── Comandos macro ───────────────────────────────


@macro_app.command("fetch")
def macro_fetch(
    source: str = typer.Option(
        "world_bank",
        "--source",
        "-s",
        help="Fuente de datos",
    ),
    indicator: str | None = typer.Option(
        None,
        "--indicator",
        "-i",
        help="Código de indicador específico (ej: NY.GDP.MKTP.CD)",
    ),
    countries: str | None = typer.Option(
        None,
        "--countries",
        "-c",
        help="Códigos ISO3 separados por coma (ej: USA,CHN,DEU)",
    ),
    start_date: str = typer.Option(
        "2000-01-01",
        "--start-date",
        help="Fecha inicio YYYY-MM-DD (solo FRED)",
    ),
) -> None:
    """Descargar datos macroeconómicos."""
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    country_list = (
        [c.strip() for c in countries.split(",")] if countries else None
    )

    if source == "world_bank":
        from stonks.fetchers.world_bank import (
            WorldBankFetcher,
        )

        fetcher = WorldBankFetcher()

        if indicator:
            console.print(
                f"Descargando [cyan]{indicator}[/cyan] desde World Bank..."
            )
            stats = fetcher.fetch_indicator(
                indicator,
                countries=country_list,
            )
            console.print(
                f"  Descargados: {stats['fetched']}, "
                f"Insertados: {stats['inserted']}, "
                f"Actualizados: {stats['updated']}"
            )
        else:
            console.print(
                "Descargando [cyan]todos los "
                "indicadores[/cyan] desde "
                "World Bank..."
            )
            results = fetcher.fetch_all_indicators(
                countries=country_list,
            )
            total_ins = sum(r["inserted"] for r in results.values())
            total_upd = sum(r["updated"] for r in results.values())
            console.print(
                f"\n[green]✓ {len(results)} "
                f"indicadores procesados: "
                f"{total_ins} insertados, "
                f"{total_upd} actualizados[/green]"
            )
    elif source == "fred":
        from stonks.fetchers.fred import FredFetcher

        fetcher = FredFetcher()

        if not fetcher.api_key:
            console.print(
                "[red]STONKS_FRED_API_KEY no configurada en .env[/red]"
            )
            return

        if indicator:
            console.print(
                f"Descargando FRED [cyan]"
                f"{indicator}[/cyan] desde "
                f"{start_date}..."
            )
            stats = fetcher.fetch_series(
                indicator,
                indicator,
                start_date=start_date,
            )
            console.print(f"  Insertados: {stats['inserted']}")
        else:
            console.print(
                "Descargando [cyan]todas las series "
                f"FRED[/cyan] desde {start_date}..."
            )
            results = fetcher.fetch_all(
                start_date=start_date,
            )
            total_ins = sum(r["inserted"] for r in results.values())
            console.print(
                f"\n[green]✓ {len(results)} series: "
                f"{total_ins} insertados[/green]"
            )
    else:
        console.print(f"[red]Fuente '{source}' no implementada aún[/red]")


@macro_app.command("list")
def macro_list() -> None:
    """Listar indicadores disponibles."""
    from stonks.db import get_session
    from stonks.models.macro import Indicator

    session = get_session()
    indicators = (
        session.query(Indicator)
        .order_by(Indicator.category, Indicator.code)
        .all()
    )

    table = Table(title="Indicadores Macro")
    table.add_column("Código", style="cyan")
    table.add_column("Nombre")
    table.add_column("Categoría")
    table.add_column("Unidad")
    table.add_column("Frecuencia")

    for ind in indicators:
        table.add_row(
            ind.code,
            ind.name,
            ind.category or "-",
            ind.unit or "-",
            ind.frequency or "-",
        )

    session.close()
    console.print(table)


# ── Comandos equity ──────────────────────────────


@equity_app.command("fetch")
def equity_fetch(
    ticker: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Ticker específico (ej: AAPL)",
    ),
    batch: str | None = typer.Option(
        None,
        "--batch",
        "-b",
        help="sp500, eu, global, o región del YAML",
    ),
    period: str = typer.Option(
        "5y",
        "--period",
        "-p",
        help="Período: 1y, 5y, 10y, max",
    ),
) -> None:
    """Descargar precios de acciones."""
    from stonks.fetchers.yfinance_ import (
        EU_TOP,
        SP500_TOP,
        YFinanceFetcher,
        load_tickers_from_yaml,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    fetcher = YFinanceFetcher()

    if ticker:
        console.print(f"Descargando [cyan]{ticker}[/cyan]...")
        company_id = fetcher.fetch_company_info(ticker)
        stats = fetcher.fetch_prices(
            ticker,
            period=period,
            company_id=company_id,
        )
        console.print(
            f"  Insertados: {stats['inserted']}, "
            f"Actualizados: {stats['updated']}"
        )
    elif batch:
        predefined = {
            "sp500": SP500_TOP,
            "eu": EU_TOP,
            "all": SP500_TOP + EU_TOP,
            "global": None,
        }
        if batch in predefined:
            tickers = predefined[batch]
            if tickers is None:
                tickers = load_tickers_from_yaml()
        else:
            # Intentar como región del YAML
            tickers = load_tickers_from_yaml(batch)
            if not tickers:
                console.print(f"[red]Batch '{batch}' no existe[/red]")
                return
        console.print(
            f"Descargando batch [cyan]{batch}"
            f"[/cyan] ({len(tickers)} tickers)..."
        )
        results = fetcher.fetch_batch(tickers, period=period)
        total_ins = sum(r["inserted"] for r in results.values())
        console.print(
            f"\n[green]✓ {len(results)} empresas: "
            f"{total_ins} precios insertados[/green]"
        )
    else:
        console.print("[yellow]Usa --ticker o --batch[/yellow]")


@equity_app.command("fetch-tiingo")
def equity_fetch_stooq(
    ticker: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Ticker específico (ej: AAPL)",
    ),
    limite: int | None = typer.Option(
        None,
        "--limite",
        "-n",
        help="Máximo de empresas a procesar",
    ),
    sobrescribir: bool = typer.Option(
        False,
        "--sobrescribir",
        help="Pisar precios existentes en vez de solo rellenar huecos",
    ),
) -> None:
    """Rellenar huecos de precios con Tiingo (fuente secundaria)."""
    from stonks.fetchers.tiingo import TiingoFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    fetcher = TiingoFetcher()
    stats = fetcher.fetch_prices(
        ticker=ticker,
        limite=limite,
        solo_huecos=not sobrescribir,
    )
    console.print(
        f"[green]✓ {stats['empresas']} empresas, "
        f"{stats['puntos']} puntos nuevos, "
        f"{stats['errores']} errores[/green]"
    )


@equity_app.command("validar-precios")
def equity_validar_precios(
    limite: int = typer.Option(
        200,
        "--limite",
        "-n",
        help="Empresas a comparar",
    ),
) -> None:
    """Contrastar los cierres cargados contra Tiingo."""
    from stonks.fetchers.tiingo import TiingoFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    stats = TiingoFetcher().validar(limite=limite)
    color = "yellow" if stats["divergentes"] else "green"
    console.print(
        f"[{color}]{stats['comparadas']} comparadas, "
        f"{stats['divergentes']} divergentes[/{color}]"
    )


@equity_app.command("list")
def equity_list() -> None:
    """Listar empresas en la BD."""
    from stonks.db import get_session
    from stonks.models.equity import Company

    session = get_session()
    companies = session.query(Company).order_by(Company.ticker).all()

    table = Table(title="Empresas")
    table.add_column("Ticker", style="cyan")
    table.add_column("Nombre")
    table.add_column("País")
    table.add_column("Market Cap (USD)")
    table.add_column("Moneda")

    for c in companies:
        mc = f"{c.market_cap_usd:,.0f}" if c.market_cap_usd else "-"
        table.add_row(
            c.ticker,
            c.name[:50],
            c.country_code or "-",
            mc,
            c.currency_code or "-",
        )

    session.close()
    console.print(f"\nTotal: {len(companies)} empresas")
    console.print(table)


@equity_app.command("search")
def equity_search(
    query: str = typer.Argument(help="Buscar por nombre o ticker"),
) -> None:
    """Buscar empresas por nombre o ticker."""
    from stonks.db import get_session
    from stonks.models.equity import Company

    session = get_session()
    q = f"%{query}%"
    results = (
        session.query(Company)
        .filter(Company.name.ilike(q) | Company.ticker.ilike(q))
        .limit(20)
        .all()
    )

    if not results:
        console.print("[yellow]Sin resultados[/yellow]")
        session.close()
        return

    table = Table(title=f"Búsqueda: '{query}'")
    table.add_column("Ticker", style="cyan")
    table.add_column("Nombre")
    table.add_column("País")

    for c in results:
        table.add_row(
            c.ticker,
            c.name[:60],
            c.country_code or "-",
        )

    session.close()
    console.print(table)


@equity_app.command("fundamentals")
def equity_fundamentals(
    ticker: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Ticker específico",
    ),
    all_companies: bool = typer.Option(
        False,
        "--all",
        help="Todas las empresas en BD",
    ),
) -> None:
    """Descargar fundamentales (income, balance, CF,
    dividendos, splits)."""
    from stonks.fetchers.fundamentals import (
        FundamentalsFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    fetcher = FundamentalsFetcher()

    if ticker:
        console.print(f"Fundamentales [cyan]{ticker}[/cyan]...")
        results = fetcher.fetch_all_for_company(ticker)
        fin = results["financials"]
        div = results["dividends"]
        spl = results["splits"]
        console.print(
            f"  Financieros: {fin['inserted']} ins, "
            f"Dividendos: {div['inserted']} ins, "
            f"Splits: {spl['inserted']} ins"
        )
    elif all_companies:
        console.print(
            "Descargando fundamentales para [cyan]todas[/cyan] las empresas..."
        )
        results = fetcher.fetch_batch()
        total = sum(r["financials"]["inserted"] for r in results.values())
        console.print(
            f"\n[green]✓ {len(results)} empresas: "
            f"{total} registros financieros"
            f"[/green]"
        )
    else:
        console.print("[yellow]Usa --ticker o --all[/yellow]")


# ── Comandos fi (renta fija) ─────────────────────


@fi_app.command("fetch")
def fi_fetch(
    period: str = typer.Option(
        "5y",
        "--period",
        "-p",
        help="Período: 1y, 5y, 10y, max",
    ),
) -> None:
    """Descargar curvas de tipos US Treasury."""
    from stonks.fetchers.yields import (
        YieldCurveFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    console.print("Descargando [cyan]US Treasury Yields[/cyan]...")
    fetcher = YieldCurveFetcher()
    stats = fetcher.fetch_us_yields(period=period)
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


@fi_app.command("seed")
def fi_seed() -> None:
    """Poblar emisores soberanos G20+."""
    from stonks.fetchers.bonds import BondFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    console.print("Insertando [cyan]emisores soberanos[/cyan]...")
    fetcher = BondFetcher()
    stats = fetcher.seed_government_issuers()
    console.print(f"  Insertados: {stats['inserted']}")


@fi_app.command("bonds")
def fi_bonds() -> None:
    """Descargar bonos US Treasury."""
    from stonks.fetchers.bonds import BondFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    console.print("Descargando [cyan]bonos US Treasury[/cyan]...")
    fetcher = BondFetcher()
    stats = fetcher.fetch_us_bonds()
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


@fi_app.command("ratings")
def fi_ratings() -> None:
    """Descargar ratings soberanos (Fitch)."""
    from stonks.fetchers.bonds import BondFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    console.print("Descargando [cyan]ratings soberanos[/cyan]...")
    fetcher = BondFetcher()
    stats = fetcher.fetch_sovereign_ratings()
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


# ── Comandos commodity ───────────────────────────


@commodity_app.command("fetch")
def commodity_fetch(
    code: str | None = typer.Option(
        None,
        "--code",
        "-c",
        help="Código commodity (ej: GOLD, WTI)",
    ),
    period: str = typer.Option(
        "5y",
        "--period",
        "-p",
    ),
) -> None:
    """Descargar precios de materias primas."""
    from stonks.fetchers.commodities import (
        CommodityFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    fetcher = CommodityFetcher()

    # Seed commodities si no existen
    n_seed = fetcher.seed_commodities()
    if n_seed:
        console.print(f"  Commodities registradas: {n_seed}")

    label = code or "todas"
    console.print(f"Descargando precios [cyan]{label}[/cyan]...")
    stats = fetcher.fetch_prices(code=code, period=period)
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


@commodity_app.command("list")
def commodity_list() -> None:
    """Listar commodities en la BD."""
    from stonks.db import get_session
    from stonks.models.commodity import Commodity

    session = get_session()
    comms = (
        session.query(Commodity)
        .order_by(Commodity.category, Commodity.code)
        .all()
    )

    table = Table(title="Commodities")
    table.add_column("Código", style="cyan")
    table.add_column("Nombre")
    table.add_column("Categoría")
    table.add_column("Unidad")

    for c in comms:
        table.add_row(
            c.code,
            c.name,
            c.category or "-",
            c.unit or "-",
        )

    session.close()
    console.print(table)


# ── Comandos forex ───────────────────────────────


@forex_app.command("fetch")
def forex_fetch(
    full: bool = typer.Option(
        False,
        "--full",
        help="Histórico completo (desde 1999)",
    ),
) -> None:
    """Descargar tipos de cambio del ECB."""
    from stonks.fetchers.ecb import ECBForexFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    label = "completo" if full else "90 días"
    console.print(f"Descargando forex ECB [cyan]({label})[/cyan]...")
    fetcher = ECBForexFetcher()
    stats = fetcher.fetch_rates(full_history=full)
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


@forex_app.command("list")
def forex_list() -> None:
    """Listar pares de divisas."""
    from stonks.db import get_session
    from stonks.models.forex import CurrencyPair

    session = get_session()
    pairs = (
        session.query(CurrencyPair)
        .order_by(
            CurrencyPair.category,
            CurrencyPair.pair_code,
        )
        .all()
    )

    table = Table(title="Pares Forex")
    table.add_column("Par", style="cyan")
    table.add_column("Base")
    table.add_column("Quote")
    table.add_column("Categoría")

    for p in pairs:
        table.add_row(
            p.pair_code,
            p.base_currency,
            p.quote_currency,
            p.category or "-",
        )

    session.close()
    console.print(table)


@forex_app.command("fetch-yf")
def forex_fetch_yf(
    pair: str | None = typer.Option(
        None,
        "--pair",
        "-p",
        help="Par específico (ej: USDJPY)",
    ),
    period: str = typer.Option(
        "max",
        "--period",
        help="Periodo yfinance",
    ),
) -> None:
    """Descargar forex OHLC via yfinance (USD/XXX + crosses)."""
    from stonks.fetchers.yfinance_forex import (
        YFinanceForexFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    label = pair or "todos (25 pares)"
    console.print(
        f"Descargando forex yfinance [cyan]{label}[/cyan] period={period}..."
    )
    fetcher = YFinanceForexFetcher()
    stats = fetcher.fetch(pair_code=pair, period=period)
    console.print(f"  Puntos: {stats['puntos']}, Errores: {stats['errores']}")


# ── Comandos crypto ──────────────────────────────


@crypto_app.command("fetch")
def crypto_fetch(
    coin: str | None = typer.Option(
        None,
        "--coin",
        "-c",
        help="CoinGecko ID (ej: bitcoin)",
    ),
    days: int = typer.Option(
        365,
        "--days",
        "-d",
        help="Días de historial",
    ),
) -> None:
    """Descargar precios de criptomonedas."""
    from stonks.fetchers.coingecko import (
        CoinGeckoFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    fetcher = CoinGeckoFetcher()
    n_seed = fetcher.seed_coins()
    if n_seed:
        console.print(f"  Coins registradas: {n_seed}")

    label = coin or "todas (top 100)"
    console.print(f"Descargando crypto [cyan]{label}[/cyan]...")
    stats = fetcher.fetch_prices(coin_id=coin, days=days)
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


@crypto_app.command("fetch-yf")
def crypto_fetch_yf(
    symbol: str | None = typer.Option(
        None,
        "--symbol",
        "-s",
        help="Símbolo (ej: BTC)",
    ),
    period: str = typer.Option(
        "max",
        "--period",
        "-p",
        help="Periodo yfinance (max, 5y, 1y...)",
    ),
) -> None:
    """Descargar OHLCV crypto via yfinance (hist. completo)."""
    from stonks.fetchers.coingecko import CoinGeckoFetcher
    from stonks.fetchers.crypto_yfinance import (
        CryptoYFinanceFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    cg = CoinGeckoFetcher()
    n_seed = cg.seed_coins()
    if n_seed:
        console.print(f"  Coins registradas: {n_seed}")

    label = symbol or "todas"
    console.print(
        f"Descargando crypto yfinance [cyan]{label}[/cyan] period={period}..."
    )
    fetcher = CryptoYFinanceFetcher()
    stats = fetcher.fetch(symbol=symbol, period=period)
    console.print(f"  Puntos: {stats['puntos']}, Errores: {stats['errores']}")


# ── Comandos fund ────────────────────────────────


@fund_app.command("fetch")
def fund_fetch(
    ticker: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Ticker ETF específico",
    ),
    period: str = typer.Option(
        "5y",
        "--period",
        "-p",
    ),
) -> None:
    """Descargar NAV de ETFs/fondos."""
    from stonks.fetchers.funds import FundFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    fetcher = FundFetcher()
    n_seed = fetcher.seed_funds()
    if n_seed:
        console.print(f"  ETFs registrados: {n_seed}")

    label = ticker or "todos (25 ETFs)"
    console.print(f"Descargando ETFs [cyan]{label}[/cyan]...")
    stats = fetcher.fetch_nav(ticker=ticker, period=period)
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


@fund_app.command("list")
def fund_list() -> None:
    """Listar ETFs/fondos."""
    from stonks.db import get_session
    from stonks.models.fund import Fund

    session = get_session()
    funds = session.query(Fund).order_by(Fund.asset_class, Fund.ticker).all()

    table = Table(title="ETFs / Fondos")
    table.add_column("Ticker", style="cyan")
    table.add_column("Nombre")
    table.add_column("Clase")
    table.add_column("Geografía")
    table.add_column("Provider")

    for f in funds:
        table.add_row(
            f.ticker or "-",
            f.name[:40],
            f.asset_class or "-",
            f.geography or "-",
            f.provider or "-",
        )

    session.close()
    console.print(table)


# ── Comandos country ─────────────────────────────


@country_app.command("fetch")
def country_fetch() -> None:
    """Descargar perfiles de país y demografía."""
    from stonks.fetchers.country import (
        CountryProfileFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    fetcher = CountryProfileFetcher()

    console.print("Descargando [cyan]perfiles de país[/cyan]...")
    stats = fetcher.fetch_profiles()
    console.print(
        f"  Perfiles: {stats['inserted']} nuevos, "
        f"{stats['updated']} actualizados"
    )

    console.print("Descargando [cyan]demografía[/cyan]...")
    stats2 = fetcher.fetch_demographics()
    console.print(f"  Demografía: {stats2['inserted']} insertados")


# ── Comandos alt ─────────────────────────────────


@alt_app.command("fetch")
def alt_fetch(
    period: str = typer.Option(
        "5y",
        "--period",
        "-p",
    ),
) -> None:
    """Descargar datos alternativos (VIX, etc.)."""
    from stonks.fetchers.sentiment import (
        SentimentFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    console.print("Descargando [cyan]sentimiento/VIX[/cyan]...")
    fetcher = SentimentFetcher()
    stats = fetcher.fetch_sentiment(period=period)
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


# ── Comandos index ───────────────────────────────


@index_app.command("fetch")
def index_fetch(
    code: str | None = typer.Option(
        None,
        "--code",
        "-c",
        help="Código índice (ej: SPX, DAX)",
    ),
    period: str = typer.Option(
        "5y",
        "--period",
        "-p",
    ),
) -> None:
    """Descargar precios de índices de mercado."""
    from stonks.fetchers.indices import IndexFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    fetcher = IndexFetcher()
    n_seed = fetcher.seed_indices()
    if n_seed:
        console.print(f"  Índices registrados: {n_seed}")

    label = code or "todos (20 índices)"
    console.print(f"Descargando índices [cyan]{label}[/cyan]...")
    stats = fetcher.fetch_prices(code=code, period=period)
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


@index_app.command("list")
def index_list() -> None:
    """Listar índices de mercado."""
    from stonks.db import get_session
    from stonks.models.equity import MarketIndex

    session = get_session()
    indices = session.query(MarketIndex).order_by(MarketIndex.code).all()

    table = Table(title="Índices de Mercado")
    table.add_column("Código", style="cyan")
    table.add_column("Nombre")
    table.add_column("País")
    table.add_column("Moneda")

    for idx in indices:
        table.add_row(
            idx.code,
            idx.name,
            idx.country_code or "-",
            idx.currency_code or "-",
        )

    session.close()
    console.print(table)


# ── Comandos deriv ──────────────────────────────


@deriv_app.command("vol-fetch")
def deriv_vol_fetch(
    code: str | None = typer.Option(
        None,
        "--code",
        "-c",
        help="Código índice (ej: VIX, VVIX)",
    ),
    period: str = typer.Option(
        "5y",
        "--period",
        "-p",
    ),
) -> None:
    """Descargar índices de volatilidad."""
    from stonks.fetchers.volatility import (
        VolatilityFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    fetcher = VolatilityFetcher()
    n_seed = fetcher.seed_indices()
    if n_seed:
        console.print(f"  Índices vol registrados: {n_seed}")

    label = code or "todos (12 índices)"
    console.print(f"Descargando volatilidad [cyan]{label}[/cyan]...")
    stats = fetcher.fetch_prices(code=code, period=period)
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


@deriv_app.command("futures-fetch")
def deriv_futures_fetch(
    code: str | None = typer.Option(
        None,
        "--code",
        "-c",
        help="Código contrato (ej: ES, NQ, ZN)",
    ),
    period: str = typer.Option(
        "5y",
        "--period",
        "-p",
    ),
) -> None:
    """Descargar precios de futuros."""
    from stonks.fetchers.index_futures import (
        IndexFuturesFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    fetcher = IndexFuturesFetcher()
    n_seed = fetcher.seed_contracts()
    if n_seed:
        console.print(f"  Contratos registrados: {n_seed}")

    label = code or "todos (16 contratos)"
    console.print(f"Descargando futuros [cyan]{label}[/cyan]...")
    stats = fetcher.fetch_prices(code=code, period=period)
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


@deriv_app.command("list")
def deriv_list() -> None:
    """Listar volatilidad y futuros en la BD."""
    from stonks.db import get_session
    from stonks.models.deriv import (
        FuturesContract,
        VolatilityIndex,
    )

    session = get_session()

    vol_indices = (
        session.query(VolatilityIndex).order_by(VolatilityIndex.code).all()
    )
    table = Table(title="Índices de Volatilidad")
    table.add_column("Código", style="cyan")
    table.add_column("Nombre")
    table.add_column("Subyacente")
    table.add_column("Ticker YF")
    for v in vol_indices:
        table.add_row(
            v.code,
            v.name,
            v.underlying or "-",
            v.yfinance_ticker or "-",
        )
    console.print(table)

    contracts = (
        session.query(FuturesContract)
        .order_by(
            FuturesContract.category,
            FuturesContract.code,
        )
        .all()
    )
    table2 = Table(title="Contratos de Futuros")
    table2.add_column("Código", style="cyan")
    table2.add_column("Nombre")
    table2.add_column("Categoría")
    table2.add_column("Ticker YF")
    for c in contracts:
        table2.add_row(
            c.code,
            c.name,
            c.category or "-",
            c.yfinance_ticker or "-",
        )
    console.print(table2)

    session.close()


# ── Comandos intraday ───────────────────────────


@intraday_app.command("fetch")
def intraday_fetch(
    domain: str = typer.Option(
        "equity",
        "--domain",
        "-d",
        help="Dominio: equity, crypto, forex, commodity",
    ),
    interval: str = typer.Option(
        "1h",
        "--interval",
        "-i",
        help="Intervalo: 1m, 5m, 1h",
    ),
    tickers: str | None = typer.Option(
        None,
        "--tickers",
        "-t",
        help="Tickers separados por coma (equity)",
    ),
    top: int | None = typer.Option(
        None,
        "--top",
        "-n",
        help="Top N tickers por volumen (equity)",
    ),
) -> None:
    """Descargar datos intraday."""
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")

    if domain == "equity":
        from sqlalchemy import text

        from stonks.db import engine
        from stonks.fetchers.intraday import (
            IntradayFetcher,
        )

        if tickers:
            tk_list = [t.strip() for t in tickers.split(",")]
        elif top:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT c.ticker FROM "
                        "equity.company c "
                        "JOIN equity.price_daily p "
                        "  ON p.company_id = c.id "
                        "GROUP BY c.ticker "
                        "ORDER BY AVG(p.volume) DESC "
                        "LIMIT :n"
                    ),
                    {"n": top},
                ).fetchall()
            tk_list = [r[0] for r in rows]
        else:
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT ticker FROM equity.company")
                ).fetchall()
            tk_list = [r[0] for r in rows]

        console.print(
            f"Intraday equity {interval}: "
            f"[cyan]{len(tk_list)} tickers[/cyan]..."
        )
        fetcher = IntradayFetcher()
        stats = fetcher.fetch(tickers=tk_list, interval=interval)
        console.print(
            f"  Fetched: {stats['fetched']}, Upserted: {stats['upserted']}"
        )
    else:
        from stonks.fetchers.intraday_multi import (
            IntradayMultiFetcher,
        )

        tk_list_multi = None
        if tickers:
            tk_list_multi = [t.strip() for t in tickers.split(",")]
        console.print(
            f"Intraday {domain} {interval}: "
            f"[cyan]{'custom' if tk_list_multi else 'todos'}[/cyan]..."
        )
        fetcher_m = IntradayMultiFetcher()
        stats = fetcher_m.fetch(
            domain=domain,
            interval=interval,
            tickers=tk_list_multi,
        )
        console.print(
            f"  Fetched: {stats['fetched']}, Upserted: {stats['upserted']}"
        )


@intraday_app.command("cleanup")
def intraday_cleanup() -> None:
    """Eliminar datos intraday expirados."""
    from stonks.db import engine
    from stonks.logger import setup_logger
    from stonks.utils.partitions import (
        cleanup_intraday,
        drop_empty_partitions,
    )

    setup_logger("stonks.partitions")

    console.print("Limpiando datos intraday expirados...")
    stats = cleanup_intraday(engine)
    for k, v in stats.items():
        if v > 0:
            console.print(f"  {k}: {v:,}")

    console.print("Eliminando particiones vacías...")
    dropped = drop_empty_partitions(engine)
    if dropped:
        for p in dropped:
            console.print(f"  Eliminada: {p}")
    else:
        console.print("  Sin particiones vacías")

    console.print("[green]✓ Cleanup completado[/green]")


@intraday_app.command("partitions")
def intraday_partitions(
    months_ahead: int = typer.Option(3, "--ahead", help="Meses a crear"),
) -> None:
    """Crear particiones mensuales intraday."""
    from stonks.db import engine
    from stonks.logger import setup_logger
    from stonks.utils.partitions import (
        ensure_partitions,
    )

    setup_logger("stonks.partitions")

    console.print("Asegurando particiones intraday...")
    created = ensure_partitions(engine, months_ahead=months_ahead)
    if created:
        console.print(f"  [green]{len(created)} particiones creadas[/green]")
        for p in created[:10]:
            console.print(f"    {p}")
        if len(created) > 10:
            console.print(f"    ... y {len(created) - 10} más")
    else:
        console.print("  Todas las particiones ya existen")


# ── Dominios incorporados en la auditoria 2026-08 ────


@deriv_app.command("cot-fetch")
def deriv_cot_fetch(
    desde: str | None = typer.Option(
        None,
        "--desde",
        "-d",
        help="Fecha minima YYYY-MM-DD (por defecto, incremental)",
    ),
) -> None:
    """Descargar el informe COT de posicionamiento (CFTC)."""
    from stonks.fetchers.cftc_cot import CftcCotFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")
    stats = CftcCotFetcher().fetch(desde=desde)
    console.print(
        f"[green]✓ {stats['contratos']} contratos, "
        f"{stats['informes']} informes[/green]"
    )


@equity_app.command("constituents-world")
def equity_constituents_world(
    indice: list[str] = typer.Option(
        None, "--indice", "-i", help="Codigos de indice (repetible)"
    ),
    con_precios: bool = typer.Option(
        False,
        "--con-precios",
        help="Descargar tambien el historico de las empresas nuevas",
    ),
) -> None:
    """Cargar constituyentes de los indices mundiales."""
    from stonks.fetchers.index_constituents import (
        IndexConstituentsFetcher,
    )
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")
    stats = IndexConstituentsFetcher().fetch(
        indices=list(indice) if indice else None,
        con_precios=con_precios,
    )
    console.print(
        f"[green]✓ {stats['indices']} indices, "
        f"{stats['empresas_nuevas']} empresas nuevas, "
        f"{stats['vinculos']} vinculos[/green]"
    )
    if stats["sin_tabla"]:
        console.print(
            f"[yellow]Sin tabla legible: "
            f"{', '.join(stats['sin_tabla'])}[/yellow]"
        )


@equity_app.command("factors-fetch")
def equity_factors_fetch() -> None:
    """Descargar los factores de Fama-French por region."""
    from stonks.fetchers.fama_french import FamaFrenchFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")
    stats = FamaFrenchFetcher().fetch()
    console.print(
        f"[green]✓ {stats['observaciones']} observaciones, "
        f"{stats['series']} series[/green]"
    )


@fi_app.command("risk-premium-fetch")
def fi_risk_premium_fetch(
    anio: int | None = typer.Option(
        None, "--anio", "-a", help="Ejercicio a cargar"
    ),
) -> None:
    """Descargar primas de riesgo pais y tipos de sociedades."""
    from stonks.fetchers.damodaran import DamodaranFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")
    stats = DamodaranFetcher().fetch(anio=anio)
    console.print(
        f"[green]✓ {stats['primas']} primas de riesgo, "
        f"{stats['tipos']} tipos impositivos[/green]"
    )


@realestate_app.command("fetch")
def realestate_fetch(
    pais: list[str] = typer.Option(
        None, "--pais", "-c", help="Codigos ISO3 (repetible)"
    ),
) -> None:
    """Descargar indices de precios de vivienda."""
    from stonks.fetchers.realestate import RealEstateFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")
    stats = RealEstateFetcher().fetch(paises=list(pais) if pais else None)
    console.print(
        f"[green]✓ {stats['indices']} indices, "
        f"{stats['observaciones']} observaciones[/green]"
    )


@calendar_app.command("fetch")
def calendar_fetch(
    desde: str = typer.Option(
        "2015-01-01", "--desde", "-d", help="Fecha inicial"
    ),
) -> None:
    """Descargar el calendario de publicaciones macro (FRED)."""
    from stonks.fetchers.calendar_fred import CalendarFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")
    stats = CalendarFetcher().fetch(desde=desde)
    console.print(
        f"[green]✓ {stats['publicaciones']} publicaciones, "
        f"{stats['fechas']} fechas[/green]"
    )


@ref_app.command("lei-fetch")
def ref_lei_fetch(
    limite: int = typer.Option(
        200, "--limite", "-n", help="Empresas a resolver en esta pasada"
    ),
) -> None:
    """Asignar identificadores LEI a las empresas (GLEIF)."""
    from stonks.fetchers.gleif import GleifFetcher
    from stonks.logger import setup_logger

    setup_logger("stonks.fetch")
    stats = GleifFetcher().enlazar_empresas(limite=limite)
    console.print(
        f"[green]✓ {stats['enlazadas']} enlazadas[/green] de "
        f"{stats['buscadas']} ({stats['sin_match']} sin coincidencia)"
    )
