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

    label = coin or "todas (top 30)"
    console.print(f"Descargando crypto [cyan]{label}[/cyan]...")
    stats = fetcher.fetch_prices(coin_id=coin, days=days)
    console.print(
        f"  Insertados: {stats['inserted']}, Errores: {stats['errors']}"
    )


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
