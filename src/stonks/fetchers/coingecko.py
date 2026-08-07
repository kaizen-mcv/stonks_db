"""Fetcher de criptomonedas desde CoinGecko (free)."""

from datetime import date

from sqlalchemy.dialects.postgresql import insert

import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.crypto import (
    Coin,
    CryptoPrice,
    MarketDominance,
)

# Top 100 coins por market cap (coingecko IDs)
# (coingecko_id, symbol, nombre, categoría)
TOP_COINS = [
    # ── Layer 1 principales ──────────────────
    ("bitcoin", "BTC", "Bitcoin", "layer1"),
    ("ethereum", "ETH", "Ethereum", "layer1"),
    ("binancecoin", "BNB", "BNB", "layer1"),
    ("solana", "SOL", "Solana", "layer1"),
    ("ripple", "XRP", "XRP", "layer1"),
    ("cardano", "ADA", "Cardano", "layer1"),
    ("avalanche-2", "AVAX", "Avalanche", "layer1"),
    ("tron", "TRX", "TRON", "layer1"),
    ("polkadot", "DOT", "Polkadot", "layer1"),
    ("litecoin", "LTC", "Litecoin", "layer1"),
    ("bitcoin-cash", "BCH", "Bitcoin Cash", "layer1"),
    ("stellar", "XLM", "Stellar", "layer1"),
    ("cosmos", "ATOM", "Cosmos", "layer1"),
    ("monero", "XMR", "Monero", "layer1"),
    ("ethereum-classic", "ETC", "Ethereum Classic", "layer1"),
    ("algorand", "ALGO", "Algorand", "layer1"),
    ("sui", "SUI", "Sui", "layer1"),
    ("near", "NEAR", "NEAR Protocol", "layer1"),
    ("internet-computer", "ICP", "Internet Computer", "layer1"),
    ("aptos", "APT", "Aptos", "layer1"),
    ("hedera-hashgraph", "HBAR", "Hedera", "layer1"),
    ("kaspa", "KAS", "Kaspa", "layer1"),
    ("vechain", "VET", "VeChain", "layer1"),
    ("fantom", "FTM", "Fantom", "layer1"),
    ("the-open-network", "TON", "Toncoin", "layer1"),
    ("sei-network", "SEI", "Sei", "layer1"),
    ("elrond-erd-2", "EGLD", "MultiversX", "layer1"),
    ("eos", "EOS", "EOS", "layer1"),
    ("neo", "NEO", "Neo", "layer1"),
    ("zilliqa", "ZIL", "Zilliqa", "layer1"),
    ("iota", "IOTA", "IOTA", "layer1"),
    ("flow-token", "FLOW", "Flow", "layer1"),
    ("mina-protocol", "MINA", "Mina", "layer1"),
    ("tezos", "XTZ", "Tezos", "layer1"),
    ("kava", "KAVA", "Kava", "layer1"),
    # ── Stablecoins ──────────────────────────
    ("tether", "USDT", "Tether", "stablecoin"),
    ("usd-coin", "USDC", "USD Coin", "stablecoin"),
    ("dai", "DAI", "Dai", "stablecoin"),
    ("first-digital-usd", "FDUSD", "First Digital USD", "stablecoin"),
    # ── Meme ─────────────────────────────────
    ("dogecoin", "DOGE", "Dogecoin", "meme"),
    ("shiba-inu", "SHIB", "Shiba Inu", "meme"),
    ("pepe", "PEPE", "Pepe", "meme"),
    ("floki", "FLOKI", "FLOKI", "meme"),
    ("bonk", "BONK", "Bonk", "meme"),
    # ── DeFi ─────────────────────────────────
    ("chainlink", "LINK", "Chainlink", "defi"),
    ("uniswap", "UNI", "Uniswap", "defi"),
    ("aave", "AAVE", "Aave", "defi"),
    ("maker", "MKR", "Maker", "defi"),
    ("lido-dao", "LDO", "Lido DAO", "defi"),
    ("the-graph", "GRT", "The Graph", "defi"),
    ("pancakeswap-token", "CAKE", "PancakeSwap", "defi"),
    ("curve-dao-token", "CRV", "Curve DAO", "defi"),
    ("compound-governance-token", "COMP", "Compound", "defi"),
    ("synthetix-network-token", "SNX", "Synthetix", "defi"),
    ("1inch", "1INCH", "1inch", "defi"),
    ("sushi", "SUSHI", "SushiSwap", "defi"),
    ("jupiter-exchange-solana", "JUP", "Jupiter", "defi"),
    ("pendle", "PENDLE", "Pendle", "defi"),
    ("ondo-finance", "ONDO", "Ondo Finance", "defi"),
    ("ethena", "ENA", "Ethena", "defi"),
    ("raydium", "RAY", "Raydium", "defi"),
    # ── Layer 2 ──────────────────────────────
    ("polygon-ecosystem-token", "POL", "Polygon", "layer2"),
    ("arbitrum", "ARB", "Arbitrum", "layer2"),
    ("optimism", "OP", "Optimism", "layer2"),
    ("starknet", "STRK", "Starknet", "layer2"),
    ("immutable-x", "IMX", "Immutable X", "layer2"),
    ("mantle", "MNT", "Mantle", "layer2"),
    # ── Infra / Storage / Compute ────────────
    ("filecoin", "FIL", "Filecoin", "infra"),
    ("render-token", "RENDER", "Render", "infra"),
    ("arweave", "AR", "Arweave", "infra"),
    ("theta-token", "THETA", "Theta Network", "infra"),
    ("helium", "HNT", "Helium", "infra"),
    ("akash-network", "AKT", "Akash Network", "infra"),
    # ── Exchange tokens ──────────────────────
    ("okb", "OKB", "OKB", "exchange"),
    ("crypto-com-chain", "CRO", "Cronos", "exchange"),
    ("leo-token", "LEO", "UNUS SED LEO", "exchange"),
    ("kucoin-shares", "KCS", "KuCoin Token", "exchange"),
    ("gatechain-token", "GT", "Gate Token", "exchange"),
    # ── Gaming / Metaverso ───────────────────
    ("axie-infinity", "AXS", "Axie Infinity", "gaming"),
    ("the-sandbox", "SAND", "The Sandbox", "gaming"),
    ("decentraland", "MANA", "Decentraland", "gaming"),
    ("gala", "GALA", "Gala", "gaming"),
    ("enjincoin", "ENJ", "Enjin Coin", "gaming"),
    # ── Interoperabilidad ────────────────────
    ("quant-network", "QNT", "Quant", "interop"),
    ("thorchain", "RUNE", "THORChain", "interop"),
    ("wormhole", "W", "Wormhole", "interop"),
    # ── Privacy ──────────────────────────────
    ("zcash", "ZEC", "Zcash", "privacy"),
    ("dash", "DASH", "Dash", "privacy"),
    # ── AI / Data ────────────────────────────
    ("fetch-ai", "FET", "Fetch.ai", "ai"),
    ("singularitynet", "AGIX", "SingularityNET", "ai"),
    ("ocean-protocol", "OCEAN", "Ocean Protocol", "ai"),
    ("bittensor", "TAO", "Bittensor", "ai"),
    # ── Otros relevantes ─────────────────────
    ("worldcoin-wld", "WLD", "Worldcoin", "identity"),
    ("celestia", "TIA", "Celestia", "modular"),
    ("injective-protocol", "INJ", "Injective", "layer1"),
    ("pyth-network", "PYTH", "Pyth Network", "oracle"),
]


class CoinGeckoFetcher(BaseFetcher):
    """Descarga datos crypto de CoinGecko."""

    SOURCE_NAME = "coingecko"
    DOMAIN = "crypto"
    RATE_LIMIT = 1.0  # con API key: ~30 req/min
    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self) -> None:
        super().__init__()
        from stonks.config import settings

        if settings.coingecko_key:
            self._session.headers.update(
                {
                    "x-cg-demo-api-key": (settings.coingecko_key),
                }
            )

    def seed_coins(self) -> int:
        """Insertar coins de referencia."""
        session = get_session()
        count = 0
        try:
            for cg_id, symbol, name, cat in TOP_COINS:
                if session.query(Coin).filter_by(coingecko_id=cg_id).first():
                    continue
                session.add(
                    Coin(
                        coingecko_id=cg_id,
                        symbol=symbol,
                        name=name,
                        category=cat,
                    )
                )
                count += 1
            session.commit()
        finally:
            session.close()
        return count

    def fetch_prices(
        self,
        coin_id: str | None = None,
        days: int = 365,
    ) -> dict[str, int]:
        """Descargar precios históricos.

        Args:
            coin_id: CoinGecko ID (ej: 'bitcoin').
                None = todas las coins registradas.
            days: Número de días de historial.
        """
        run_id = self._start_run(
            params={
                "coin_id": coin_id,
                "days": days,
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
            if coin_id:
                coins = [
                    session.query(Coin).filter_by(coingecko_id=coin_id).first()
                ]
            else:
                coins = session.query(Coin).all()

            for coin in coins:
                if not coin:
                    continue

                logger.info(
                    "  Crypto: %s (%s)...",
                    coin.name,
                    coin.symbol,
                )

                url = f"{self.BASE_URL}/coins/{coin.coingecko_id}/market_chart"
                params = {
                    "vs_currency": "usd",
                    "days": str(days),
                    "interval": "daily",
                }

                try:
                    data = self._get(url, params)
                except Exception as e:
                    logger.warning(
                        "  Error %s: %s",
                        coin.symbol,
                        e,
                    )
                    stats["errors"] += 1
                    continue

                prices = data.get("prices", [])
                volumes = data.get("total_volumes", [])
                mcaps = data.get("market_caps", [])

                vol_map = {int(v[0]): v[1] for v in volumes if v[1]}
                mcap_map = {int(m[0]): m[1] for m in mcaps if m[1]}

                # Un dict por (coin, fecha): CoinGecko puede devolver
                # varias marcas de tiempo del mismo dia y ON CONFLICT
                # no resuelve duplicados dentro del mismo INSERT.
                lote: dict[date, dict] = {}
                for point in prices:
                    ts_ms = int(point[0])
                    price = point[1]
                    if price is None:
                        continue

                    dt = date.fromtimestamp(ts_ms / 1000)
                    stats["fetched"] += 1
                    lote[dt] = {
                        "coin_id": coin.id,
                        "date": dt,
                        "close": price,
                        "volume_usd": vol_map.get(ts_ms),
                        "market_cap_usd": mcap_map.get(ts_ms),
                        **self.linaje(),
                    }

                if lote:
                    # Upsert, no "insertar solo si falta": si un dato
                    # esta mal cargado, hay que poder corregirlo
                    # relanzando el fetcher. Con el `continue` anterior
                    # un valor erroneo se quedaba para siempre.
                    stmt = insert(CryptoPrice).values(list(lote.values()))
                    stmt = stmt.on_conflict_do_update(
                        constraint="price_daily_coin_id_date_key",
                        set_={
                            "close": stmt.excluded.close,
                            "volume_usd": stmt.excluded.volume_usd,
                            "market_cap_usd": stmt.excluded.market_cap_usd,
                            "source_id": stmt.excluded.source_id,
                            "fetch_run_id": stmt.excluded.fetch_run_id,
                        },
                    )
                    session.execute(stmt)
                    stats["inserted"] += len(lote)

                session.commit()

            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error("Error crypto: %s", e)
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats

    def fetch_market_dominance(self) -> dict:
        """Descargar snapshot del mercado crypto global."""
        url = f"{self.BASE_URL}/global"
        self._rate_limit()
        data = self._get(url)
        gd = data.get("data", {})

        total_mc = gd.get("total_market_cap", {}).get("usd")
        btc_pct = gd.get("market_cap_percentage", {}).get("btc")
        eth_pct = gd.get("market_cap_percentage", {}).get("eth")

        if total_mc is None:
            logger.warning("Sin datos de dominance")
            return {"inserted": 0}

        session = get_session()
        try:
            today = date.today()
            exists = (
                session.query(MarketDominance).filter_by(date=today).first()
            )
            if exists:
                exists.total_market_cap_usd = total_mc
                exists.btc_dominance_pct = btc_pct
                exists.eth_dominance_pct = eth_pct
            else:
                session.add(
                    MarketDominance(
                        date=today,
                        total_market_cap_usd=total_mc,
                        btc_dominance_pct=btc_pct,
                        eth_dominance_pct=eth_pct,
                    )
                )
            session.commit()
            logger.info(
                "MarketDominance %s: MC=%.0f BTC=%.1f%% ETH=%.1f%%",
                today,
                total_mc,
                btc_pct or 0,
                eth_pct or 0,
            )
        finally:
            session.close()

        return {"inserted": 1}
