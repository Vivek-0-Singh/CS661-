"""Etherscan API client — gas oracle and ETH price."""
import requests
from crypto_crush.config import ETHERSCAN_API_KEY, ETHERSCAN_URL, GWEI_FALLBACK
from crypto_crush.data.cache import Cache
from crypto_crush.config import CACHE_DIR

_cache = Cache(CACHE_DIR, max_age_hours=0.1)   # gas data stales in ~6 min
_session = requests.Session()


def _call(params: dict) -> dict:
    params["apikey"] = ETHERSCAN_API_KEY
    params.setdefault("chainid", "1")   # Ethereum mainnet (required by V2 API)
    resp = _session.get(ETHERSCAN_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result")
    # V2 returns status "0" with a string result on error
    if str(data.get("status", "1")) == "0" or not isinstance(result, dict):
        raise ValueError(f"Etherscan error: {result}")
    return data


def get_gas_price_gwei() -> float:
    """Return current fast gas price in Gwei."""
    cached = _cache.get("gas_price")
    if cached is not None:
        return float(cached)
    try:
        data = _call({"module": "gastracker", "action": "gasoracle"})
        gwei = float(data["result"]["FastGasPrice"])
        _cache.set("gas_price", gwei)
        print(f"  Gas oracle: {gwei:.1f} Gwei (fast)")
        return gwei
    except Exception as e:
        print(f"  [warn] Gas oracle failed ({e}), using fallback {GWEI_FALLBACK} Gwei")
        return float(GWEI_FALLBACK)


def get_eth_price_usd() -> float:
    """Return current ETH/USD price from Etherscan."""
    cached = _cache.get("eth_price_live")
    if cached is not None:
        return float(cached)
    try:
        data = _call({"module": "stats", "action": "ethprice"})
        price = float(data["result"]["ethusd"])
        _cache.set("eth_price_live", price)
        return price
    except Exception as e:
        print(f"  [warn] ETH price from Etherscan failed ({e}), using 2500")
        return 2500.0


def gas_cost_usd(gas_units: int) -> float:
    """Compute USD cost of a transaction given gas units."""
    gwei = get_gas_price_gwei()
    eth_price = get_eth_price_usd()
    return gas_units * gwei * 1e-9 * eth_price
