"""Fetcher de criptomonedas desde CoinGecko (free)."""

from datetime import date

import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.crypto import (
    Coin,
    CryptoPrice,
)

# Top 50 coins por market cap (coingecko IDs)
TOP_COINS = [
    ("bitcoin", "BTC", "Bitcoin", "layer1"),
    ("ethereum", "ETH", "Ethereum", "layer1"),
    ("tether", "USDT", "Tether", "stablecoin"),
    ("binancecoin", "BNB", "BNB", "layer1"),
    ("solana", "SOL", "Solana", "layer1"),
    ("usd-coin", "USDC", "USD Coin", "stablecoin"),
    ("ripple", "XRP", "XRP", "layer1"),
    ("cardano", "ADA", "Cardano", "layer1"),
    ("dogecoin", "DOGE", "Dogecoin", "meme"),
    ("avalanche-2", "AVAX", "Avalanche", "layer1"),
    ("tron", "TRX", "TRON", "layer1"),
    ("polkadot", "DOT", "Polkadot", "layer1"),
    ("chainlink", "LINK", "Chainlink", "defi"),
    ("polygon-ecosystem-token", "POL", "Polygon", "layer2"),
    ("shiba-inu", "SHIB", "Shiba Inu", "meme"),
    ("litecoin", "LTC", "Litecoin", "layer1"),
    ("bitcoin-cash", "BCH", "Bitcoin Cash", "layer1"),
    ("uniswap", "UNI", "Uniswap", "defi"),
    ("stellar", "XLM", "Stellar", "layer1"),
    ("cosmos", "ATOM", "Cosmos", "layer1"),
    ("monero", "XMR", "Monero", "layer1"),
    ("ethereum-classic", "ETC", "Ethereum Classic", "layer1"),
    ("aave", "AAVE", "Aave", "defi"),
    ("maker", "MKR", "Maker", "defi"),
    ("algorand", "ALGO", "Algorand", "layer1"),
    ("filecoin", "FIL", "Filecoin", "infra"),
    ("arbitrum", "ARB", "Arbitrum", "layer2"),
    ("optimism", "OP", "Optimism", "layer2"),
    ("render-token", "RENDER", "Render", "infra"),
    ("sui", "SUI", "Sui", "layer1"),
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

                for point in prices:
                    ts_ms = int(point[0])
                    price = point[1]
                    if price is None:
                        continue

                    dt = date.fromtimestamp(ts_ms / 1000)
                    stats["fetched"] += 1

                    exists = (
                        session.query(CryptoPrice)
                        .filter_by(
                            coin_id=coin.id,
                            date=dt,
                        )
                        .first()
                    )

                    if exists:
                        continue

                    session.add(
                        CryptoPrice(
                            coin_id=coin.id,
                            date=dt,
                            close=price,
                            volume_usd=vol_map.get(ts_ms),
                            market_cap_usd=mcap_map.get(ts_ms),
                        )
                    )
                    stats["inserted"] += 1

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
