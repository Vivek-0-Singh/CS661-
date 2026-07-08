"""Central configuration — API keys and runtime settings."""
import os
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent

# ── API keys ─────────────────────────────────────────────────────────────────
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "KJ3TW48XHC1FVCTVQXHWG4CIJCMZ9BPFXV")

# ── Data / cache ──────────────────────────────────────────────────────────────
CACHE_DIR = ROOT_DIR / "data" / "cache"
CACHE_MAX_AGE_HOURS = 6          # re-fetch live data after this many hours
HISTORY_DAYS = 180

# ── Backtest ──────────────────────────────────────────────────────────────────
INITIAL_CAPITAL = 100_000        # USD
RISK_FREE_RATE   = 0.05          # 5 % annual

# ── Strategy A: LP Optimizer ──────────────────────────────────────────────────
LP_FEE_TIER          = 0.0005    # Uniswap V3 0.05 % pool
LP_MIN_RANGE_WIDTH   = 0.02      # minimum ± 2 % around current price
LP_MAX_RANGE_WIDTH   = 0.60      # maximum ± 60 %
LP_VOL_ENTRY_PCTILE  = 40        # enter when 30-day vol is below this percentile
LP_VOL_EXIT_MULT     = 1.8       # exit when 5-day vol > 1.8× 30-day vol
LP_REBALANCE_DAYS    = 7         # re-check range every N days

# ── Strategy B: Yield Arbitrage ───────────────────────────────────────────────
ARB_THRESHOLD_PCT    = 0.40      # rotate when differential > 0.40 % APY
ARB_MIN_HOLD_DAYS    = 5         # minimum days before rotating again
GAS_UNITS_ROTATION   = 350_000   # gas units for a vault rotation tx
GWEI_FALLBACK        = 25        # fallback gas price if Etherscan is down

# ── Endpoint URLs ─────────────────────────────────────────────────────────────
DEFILLAMA_YIELDS_URL  = "https://yields.llama.fi"
DEFILLAMA_COINS_URL   = "https://coins.llama.fi"
ETHERSCAN_URL         = "https://api.etherscan.io/v2/api"
WETH_ADDRESS          = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
