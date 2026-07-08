"""Central configuration for CryptoLens backend."""
import os
from pathlib import Path

# Project layout ------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# CRYPTOLENS_DB lets a deploy point at a persistent-disk path (e.g. on Render).
DB_PATH = Path(os.environ["CRYPTOLENS_DB"]) if os.environ.get("CRYPTOLENS_DB") else DATA_DIR / "cryptolens.duckdb"

# Comma-separated allowed CORS origins, or "*" for any (default). Set this to
# the Vercel frontend URL in production if you want to lock it down.
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

# Assets --------------------------------------------------------------------
# display symbol -> Binance USDT trading pair
ASSETS: dict[str, str] = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
}
SYMBOLS = list(ASSETS.keys())

# Resolutions ---------------------------------------------------------------
RESOLUTIONS = {
    "1m": "1 minute",
    "1h": "1 hour",
    "1d": "1 day",
}

# Binance public data portal
VISION_BASE = "https://data.binance.vision/data/spot/monthly/klines"
