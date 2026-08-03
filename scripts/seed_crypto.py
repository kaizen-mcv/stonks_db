#!/usr/bin/env python3
"""Seed de 250+ criptomonedas en crypto.coin.

Uso:
    python scripts/seed_crypto.py [--dry-run]
"""

import argparse

from stonks.db import get_session
from stonks.logger import get_logger
from stonks.models.crypto import Coin

log = get_logger("stonks.seed_crypto")

# (coingecko_id, symbol, name, category, rank)
COINS = [
    # ── Top 10 ──────────────────────────────
    ("bitcoin", "BTC", "Bitcoin", "layer-1", 1),
    ("ethereum", "ETH", "Ethereum", "layer-1", 2),
    ("tether", "USDT", "Tether", "stablecoin", 3),
    ("binancecoin", "BNB", "BNB", "exchange", 4),
    ("solana", "SOL", "Solana", "layer-1", 5),
    ("ripple", "XRP", "XRP", "payment", 6),
    ("usd-coin", "USDC", "USD Coin", "stablecoin", 7),
    ("dogecoin", "DOGE", "Dogecoin", "meme", 8),
    ("cardano", "ADA", "Cardano", "layer-1", 9),
    ("tron", "TRX", "TRON", "layer-1", 10),
    # ── 11-25 ───────────────────────────────
    ("avalanche-2", "AVAX", "Avalanche", "layer-1", 11),
    ("shiba-inu", "SHIB", "Shiba Inu", "meme", 12),
    ("polkadot", "DOT", "Polkadot", "layer-1", 13),
    ("chainlink", "LINK", "Chainlink", "oracle", 14),
    ("bitcoin-cash", "BCH", "Bitcoin Cash", "payment", 15),
    ("near", "NEAR", "NEAR Protocol", "layer-1", 16),
    ("litecoin", "LTC", "Litecoin", "payment", 17),
    ("uniswap", "UNI", "Uniswap", "defi", 18),
    (
        "internet-computer",
        "ICP",
        "Internet Computer",
        "layer-1",
        19,
    ),
    ("dai", "DAI", "Dai", "stablecoin", 20),
    ("stellar", "XLM", "Stellar", "payment", 21),
    ("monero", "XMR", "Monero", "privacy", 22),
    (
        "ethereum-classic",
        "ETC",
        "Ethereum Classic",
        "layer-1",
        23,
    ),
    ("filecoin", "FIL", "Filecoin", "storage", 24),
    ("cosmos", "ATOM", "Cosmos", "layer-1", 25),
    # ── 26-50 ───────────────────────────────
    (
        "hedera-hashgraph",
        "HBAR",
        "Hedera",
        "layer-1",
        26,
    ),
    ("lido-dao", "LDO", "Lido DAO", "defi", 27),
    ("arbitrum", "ARB", "Arbitrum", "scaling", 28),
    ("okb", "OKB", "OKB", "exchange", 29),
    ("vechain", "VET", "VeChain", "layer-1", 30),
    ("aptos", "APT", "Aptos", "layer-1", 31),
    ("mantle", "MNT", "Mantle", "scaling", 32),
    (
        "render-token",
        "RNDR",
        "Render",
        "ai",
        33,
    ),
    (
        "injective-protocol",
        "INJ",
        "Injective",
        "defi",
        34,
    ),
    ("immutable-x", "IMX", "Immutable", "gaming", 35),
    ("optimism", "OP", "Optimism", "scaling", 36),
    ("kaspa", "KAS", "Kaspa", "layer-1", 37),
    ("the-graph", "GRT", "The Graph", "defi", 38),
    (
        "theta-token",
        "THETA",
        "Theta Network",
        "layer-1",
        39,
    ),
    ("fantom", "FTM", "Fantom", "layer-1", 40),
    ("algorand", "ALGO", "Algorand", "layer-1", 41),
    ("flow", "FLOW", "Flow", "layer-1", 42),
    ("aave", "AAVE", "Aave", "defi", 43),
    ("bittensor", "TAO", "Bittensor", "ai", 44),
    ("celestia", "TIA", "Celestia", "layer-1", 45),
    ("stacks", "STX", "Stacks", "layer-1", 46),
    ("maker", "MKR", "Maker", "defi", 47),
    ("axie-infinity", "AXS", "Axie Infinity", "gaming", 48),
    ("neo", "NEO", "Neo", "layer-1", 49),
    ("gala", "GALA", "Gala", "gaming", 50),
    # ── 51-75 ───────────────────────────────
    ("decentraland", "MANA", "Decentraland", "metaverse", 51),
    (
        "mina-protocol",
        "MINA",
        "Mina Protocol",
        "layer-1",
        52,
    ),
    ("eos", "EOS", "EOS", "layer-1", 53),
    ("kucoin-shares", "KCS", "KuCoin Token", "exchange", 54),
    ("iota", "IOTA", "IOTA", "layer-1", 55),
    ("sui", "SUI", "Sui", "layer-1", 56),
    ("sei-network", "SEI", "Sei", "layer-1", 57),
    ("jupiter-exchange-solana", "JUP", "Jupiter", "defi", 58),
    ("blur", "BLUR", "Blur", "nft", 59),
    ("ondo-finance", "ONDO", "Ondo Finance", "defi", 60),
    ("bonk", "BONK", "Bonk", "meme", 61),
    ("wormhole", "W", "Wormhole", "interop", 62),
    (
        "pyth-network",
        "PYTH",
        "Pyth Network",
        "oracle",
        63,
    ),
    ("jito-governance-token", "JTO", "Jito", "defi", 64),
    ("worldcoin-wld", "WLD", "Worldcoin", "layer-1", 65),
    ("beam-2", "BEAM", "Beam", "gaming", 66),
    ("pepe", "PEPE", "Pepe", "meme", 67),
    ("floki", "FLOKI", "Floki", "meme", 68),
    ("raydium", "RAY", "Raydium", "defi", 69),
    ("pendle", "PENDLE", "Pendle", "defi", 70),
    (
        "quant-network",
        "QNT",
        "Quant",
        "interop",
        71,
    ),
    (
        "bitcoin-cash-sv",
        "BSV",
        "Bitcoin SV",
        "payment",
        72,
    ),
    (
        "elrond-erd-2",
        "EGLD",
        "MultiversX",
        "layer-1",
        73,
    ),
    ("tezos", "XTZ", "Tezos", "layer-1", 74),
    ("the-sandbox", "SAND", "The Sandbox", "metaverse", 75),
    # ── 76-100 ──────────────────────────────
    ("enjincoin", "ENJ", "Enjin Coin", "gaming", 76),
    ("chiliz", "CHZ", "Chiliz", "gaming", 77),
    ("zcash", "ZEC", "Zcash", "privacy", 78),
    ("curve-dao-token", "CRV", "Curve DAO", "defi", 79),
    ("compound-governance-token", "COMP", "Compound", "defi", 80),
    ("kava", "KAVA", "Kava", "defi", 81),
    ("oasis-network", "ROSE", "Oasis Network", "privacy", 82),
    ("zilliqa", "ZIL", "Zilliqa", "layer-1", 83),
    ("celo", "CELO", "Celo", "layer-1", 84),
    ("havven", "SNX", "Synthetix", "defi", 85),
    ("1inch", "1INCH", "1inch", "defi", 86),
    (
        "basic-attention-token",
        "BAT",
        "Basic Attention Token",
        "defi",
        87,
    ),
    ("dydx", "DYDX", "dYdX", "defi", 88),
    ("axelar", "AXL", "Axelar", "interop", 89),
    ("jasmycoin", "JASMY", "JasmyCoin", "layer-1", 90),
    ("thorchain", "RUNE", "THORChain", "defi", 91),
    (
        "fetch-ai",
        "FET",
        "Artificial Superintelligence",
        "ai",
        92,
    ),
    (
        "ocean-protocol",
        "OCEAN",
        "Ocean Protocol",
        "ai",
        93,
    ),
    ("woo-network", "WOO", "WOO", "defi", 94),
    ("gnosis", "GNO", "Gnosis", "defi", 95),
    ("rocket-pool", "RPL", "Rocket Pool", "defi", 96),
    ("loopring", "LRC", "Loopring", "scaling", 97),
    (
        "ethereum-name-service",
        "ENS",
        "Ethereum Name Service",
        "defi",
        98,
    ),
    ("mask-network", "MASK", "Mask Network", "defi", 99),
    ("ankr", "ANKR", "Ankr", "defi", 100),
    # ── 101-150 ─────────────────────────────
    ("skale", "SKL", "SKALE", "scaling", 101),
    ("omisego", "OMG", "OMG Network", "scaling", 102),
    ("storj", "STORJ", "Storj", "storage", 103),
    ("sushi", "SUSHI", "SushiSwap", "defi", 104),
    ("uma", "UMA", "UMA", "defi", 105),
    ("0x", "ZRX", "0x", "defi", 106),
    ("yearn-finance", "YFI", "yearn.finance", "defi", 107),
    ("balancer", "BAL", "Balancer", "defi", 108),
    (
        "band-protocol",
        "BAND",
        "Band Protocol",
        "oracle",
        109,
    ),
    ("nkn", "NKN", "NKN", "layer-1", 110),
    (
        "origin-protocol",
        "OGN",
        "Origin Protocol",
        "defi",
        111,
    ),
    ("iexec-rlc", "RLC", "iExec RLC", "defi", 112),
    ("melon", "MLN", "Enzyme", "defi", 113),
    ("numeraire", "NMR", "Numeraire", "ai", 114),
    (
        "livepeer",
        "LPT",
        "Livepeer",
        "storage",
        115,
    ),
    ("api3", "API3", "API3", "oracle", 116),
    ("audius", "AUDIO", "Audius", "defi", 117),
    ("marlin", "POND", "Marlin", "layer-1", 118),
    ("cartesi", "CTSI", "Cartesi", "scaling", 119),
    ("celer-network", "CELR", "Celer Network", "scaling", 120),
    (
        "request-network",
        "REQ",
        "Request",
        "payment",
        121,
    ),
    (
        "orchid-protocol",
        "OXT",
        "Orchid",
        "privacy",
        122,
    ),
    (
        "district0x",
        "DNT",
        "district0x",
        "defi",
        123,
    ),
    ("gitcoin", "GTC", "Gitcoin", "dao", 124),
    ("radicle", "RAD", "Radicle", "defi", 125),
    ("polkastarter", "POLS", "Polkastarter", "defi", 126),
    (
        "perpetual-protocol",
        "PERP",
        "Perpetual Protocol",
        "defi",
        127,
    ),
    (
        "alpha-finance",
        "ALPHA",
        "Stella",
        "defi",
        128,
    ),
    ("badger-dao", "BADGER", "Badger DAO", "defi", 129),
    ("liquity", "LQTY", "Liquity", "defi", 130),
    (
        "convex-finance",
        "CVX",
        "Convex Finance",
        "defi",
        131,
    ),
    ("frax-share", "FXS", "Frax Share", "defi", 132),
    ("super", "SUPER", "SuperVerse", "gaming", 133),
    ("highstreet", "HIGH", "Highstreet", "metaverse", 134),
    ("alchemy-pay", "ACH", "Alchemy Pay", "payment", 135),
    ("biconomy", "BICO", "Biconomy", "scaling", 136),
    ("ethernity-chain", "ERN", "Ethernity Chain", "nft", 137),
    ("arpa", "ARPA", "ARPA", "privacy", 138),
    (
        "ampleforth-governance-token",
        "FORTH",
        "Ampleforth Governance",
        "defi",
        139,
    ),
    ("republic-protocol", "REN", "Ren", "defi", 140),
    (
        "keep3rv1",
        "KP3R",
        "Keep3rV1",
        "defi",
        141,
    ),
    ("truefi", "TRU", "TrueFi", "defi", 142),
    (
        "barnbridge",
        "BOND",
        "BarnBridge",
        "defi",
        143,
    ),
    ("idex", "IDEX", "IDEX", "defi", 144),
    ("nu-cypher", "NU", "NuCypher", "privacy", 145),
    ("dodo", "DODO", "DODO", "defi", 146),
    ("harvest-finance", "FARM", "Harvest Finance", "defi", 147),
    ("reef", "REEF", "Reef", "defi", 148),
    (
        "my-neighbor-alice",
        "ALICE",
        "My Neighbor Alice",
        "gaming",
        149,
    ),
    ("alien-worlds", "TLM", "Alien Worlds", "gaming", 150),
    # ── 151-200 ─────────────────────────────
    (
        "aavegotchi",
        "GHST",
        "Aavegotchi",
        "gaming",
        151,
    ),
    ("vulcan-forged", "PYR", "Vulcan Forged", "gaming", 152),
    ("safepal", "SFP", "SafePal", "defi", 153),
    (
        "auction",
        "AUCTION",
        "Bounce",
        "defi",
        154,
    ),
    ("unifi-protocol-dao", "UNFI", "Unifi Protocol", "defi", 155),
    ("frontier-token", "FRONT", "Frontier", "defi", 156),
    ("groestlcoin", "GRS", "Groestlcoin", "payment", 157),
    ("steem", "STEEM", "Steem", "layer-1", 158),
    ("verge", "XVG", "Verge", "privacy", 159),
    ("siacoin", "SC", "Siacoin", "storage", 160),
    ("decred", "DCR", "Decred", "layer-1", 161),
    ("waves", "WAVES", "Waves", "layer-1", 162),
    ("kadena", "KDA", "Kadena", "layer-1", 163),
    ("flux", "FLUX", "Flux", "layer-1", 164),
    ("ergo", "ERG", "Ergo", "layer-1", 165),
    ("helium", "HNT", "Helium", "layer-1", 166),
    ("iotex", "IOTX", "IoTeX", "layer-1", 167),
    ("harmony", "ONE", "Harmony", "layer-1", 168),
    ("coti", "COTI", "COTI", "payment", 169),
    ("ravencoin", "RVN", "Ravencoin", "layer-1", 170),
    ("syscoin", "SYS", "Syscoin", "layer-1", 171),
    ("nervos-network", "CKB", "Nervos Network", "layer-1", 172),
    ("icon", "ICX", "ICON", "layer-1", 173),
    ("wax", "WAXP", "WAX", "gaming", 174),
    ("ontology", "ONT", "Ontology", "layer-1", 175),
    ("qtum", "QTUM", "Qtum", "layer-1", 176),
    ("horizen", "ZEN", "Horizen", "privacy", 177),
    ("lisk", "LSK", "Lisk", "layer-1", 178),
    ("nxt", "NXT", "Nxt", "layer-1", 179),
    ("ark", "ARK", "Ark", "layer-1", 180),
    ("status", "SNT", "Status", "layer-1", 181),
    ("power-ledger", "POWR", "Powerledger", "defi", 182),
    ("civic", "CVC", "Civic", "layer-1", 183),
    ("golem", "GLM", "Golem", "defi", 184),
    ("augur", "REP", "Augur", "defi", 185),
    ("arweave", "AR", "Arweave", "storage", 186),
    (
        "singularitynet",
        "AGIX",
        "SingularityNET",
        "ai",
        187,
    ),
    ("conflux-token", "CFX", "Conflux", "layer-1", 188),
    ("ecash", "XEC", "eCash", "payment", 189),
    ("baby-doge-coin", "BABYDOGE", "Baby Doge Coin", "meme", 190),
    ("terra-luna-2", "LUNA", "Terra", "layer-1", 191),
    ("trust-wallet-token", "TWT", "Trust Wallet Token", "defi", 192),
    ("huobi-token", "HT", "Huobi Token", "exchange", 193),
    ("gate-token", "GT", "Gate", "exchange", 194),
    ("cronos", "CRO", "Cronos", "layer-1", 195),
    ("matic-network", "MATIC", "Polygon", "scaling", 196),
    ("just", "JST", "JUST", "defi", 197),
    ("apenft", "NFT", "APENFT", "nft", 198),
    ("wink", "WIN", "WINkLink", "oracle", 199),
    ("bittorrent", "BTT", "BitTorrent", "storage", 200),
    # ── 201-260 ─────────────────────────────
    ("pancakeswap-token", "CAKE", "PancakeSwap", "defi", 201),
    ("1000sats", "SATS", "1000SATS", "meme", 202),
    ("ordi", "ORDI", "ORDI", "layer-1", 203),
    ("dog-go-to-the-moon-runes", "DOG", "DOG", "meme", 204),
    ("notcoin", "NOT", "Notcoin", "meme", 205),
    ("brett", "BRETT", "Brett", "meme", 206),
    ("popcat", "POPCAT", "Popcat", "meme", 207),
    ("dogwifcoin", "WIF", "dogwifhat", "meme", 208),
    ("cat-in-a-dogs-world", "MEW", "cat in a dogs world", "meme", 209),
    ("first-digital-usd", "FDUSD", "First Digital USD", "stablecoin", 210),
    ("ethena", "ENA", "Ethena", "defi", 211),
    ("ethena-usde", "USDE", "USDe", "stablecoin", 212),
    ("aethir", "ATH", "Aethir", "ai", 213),
    ("io", "IO", "io.net", "ai", 214),
    ("echelon-prime", "PRIME", "Echelon Prime", "gaming", 215),
    ("dymension", "DYM", "Dymension", "layer-1", 216),
    ("saga-2", "SAGA", "Saga", "layer-1", 217),
    ("pixel-2", "PIXEL", "Pixels", "gaming", 218),
    ("starknet", "STRK", "Starknet", "scaling", 219),
    ("manta-network", "MANTA", "Manta Network", "scaling", 220),
    ("altlayer", "ALT", "AltLayer", "scaling", 221),
    ("xai-3", "XAI", "Xai", "gaming", 222),
    ("zeta-chain", "ZETA", "ZetaChain", "interop", 223),
    ("portal-2", "PORTAL", "Portal", "gaming", 224),
    ("sleepless-ai", "AI", "Sleepless AI", "ai", 225),
    ("nft-prompt", "NFP", "NFPrompt", "nft", 226),
    ("memecoin-2", "MEME", "Memecoin", "meme", 227),
    ("gas", "GAS", "Gas", "layer-1", 228),
    ("ssv-network", "SSV", "SSV Network", "defi", 229),
    ("polymesh", "POLYX", "Polymesh", "layer-1", 230),
    ("mog-coin", "MOG", "Mog Coin", "meme", 231),
    ("turbo", "TURBO", "Turbo", "meme", 232),
    ("ponke", "PONKE", "Ponke", "meme", 233),
    ("myro", "MYRO", "Myro", "meme", 234),
    ("wen-4", "WEN", "Wen", "meme", 235),
    ("toshi-base", "TOSHI", "Toshi", "meme", 236),
    ("degen-base", "DEGEN", "Degen", "meme", 237),
    ("wemix-token", "WEMIX", "WEMIX", "gaming", 238),
    ("coinex-token", "CET", "CoinEx Token", "exchange", 239),
    ("mx-token", "MX", "MEXC Token", "exchange", 240),
    ("leo-token", "LEO", "UNUS SED LEO", "exchange", 241),
    ("theta-fuel", "TFUEL", "Theta Fuel", "layer-1", 242),
    ("akash-network", "AKT", "Akash Network", "ai", 243),
    ("grass", "GRASS", "Grass", "ai", 251),
    ("ai16z", "AI16Z", "ai16z", "ai", 252),
    ("virtual-protocol", "VIRTUAL", "Virtuals Protocol", "ai", 253),
    ("griffain", "GRIFFAIN", "Griffain", "ai", 254),
    ("fartcoin", "FARTCOIN", "Fartcoin", "meme", 255),
    ("goatseus-maximus", "GOAT", "Goatseus Maximus", "meme", 256),
    ("pudgy-penguins", "PENGU", "Pudgy Penguins", "nft", 257),
    ("usual", "USUAL", "Usual", "defi", 258),
    ("hyperliquid", "HYPE", "Hyperliquid", "defi", 259),
    ("movement", "MOVE", "Movement", "layer-1", 260),
]


def seed(dry_run: bool = False) -> int:
    """Insertar/actualizar coins en crypto.coin."""
    session = get_session()
    new_count = 0
    updated = 0

    try:
        for cg_id, symbol, name, cat, rank in COINS:
            existing = (
                session.query(Coin).filter_by(coingecko_id=cg_id).first()
            )
            if existing:
                if existing.market_cap_rank != rank:
                    if not dry_run:
                        existing.market_cap_rank = rank
                    updated += 1
                continue

            if not dry_run:
                session.add(
                    Coin(
                        coingecko_id=cg_id,
                        symbol=symbol,
                        name=name,
                        category=cat,
                        market_cap_rank=rank,
                    )
                )
            new_count += 1

        if not dry_run:
            session.commit()

        log.info(
            "%s%d coins nuevas, %d ranks actualizados",
            "[DRY-RUN] " if dry_run else "",
            new_count,
            updated,
        )
    finally:
        session.close()

    return new_count


def main():
    parser = argparse.ArgumentParser(description="Seed 250+ criptomonedas")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar, no insertar",
    )
    args = parser.parse_args()
    seed(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
