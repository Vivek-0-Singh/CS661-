"""DefiLlama API client — pools, historical APY, and token price history."""
import time
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timezone

from crypto_crush.config import (
    CACHE_DIR, CACHE_MAX_AGE_HOURS, DEFILLAMA_YIELDS_URL,
    DEFILLAMA_COINS_URL, WETH_ADDRESS, HISTORY_DAYS,
)
from crypto_crush.data.cache import Cache

_cache = Cache(CACHE_DIR, CACHE_MAX_AGE_HOURS)
_session = requests.Session()
_session.headers.update({"User-Agent": "crypto-crush/1.0"})


def _get(url: str, cache_key: str, timeout: int = 30):
    hit = _cache.get(cache_key)
    if hit is not None:
        return hit
    resp = _session.get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    _cache.set(cache_key, data)
    return data


# ── Pool catalogue ────────────────────────────────────────────────────────────

def get_all_pools() -> list[dict]:
    data = _get(f"{DEFILLAMA_YIELDS_URL}/pools", "all_pools")
    return data.get("data", data) if isinstance(data, dict) else data


def find_pool(pools: list[dict], project: str, chain: str, symbol_fragment: str) -> dict | None:
    matches = [
        p for p in pools
        if p.get("project", "").lower() == project.lower()
        and p.get("chain", "").lower() == chain.lower()
        and symbol_fragment.lower() in p.get("symbol", "").lower()
    ]
    if not matches:
        return None
    return max(matches, key=lambda x: x.get("tvlUsd", 0))


# ── Pool history ──────────────────────────────────────────────────────────────

def get_pool_history(pool_id: str) -> pd.DataFrame:
    """Return a DataFrame with columns [timestamp, tvlUsd, apy, apyBase, apyReward]."""
    data = _get(
        f"{DEFILLAMA_YIELDS_URL}/chart/{pool_id}",
        f"pool_hist_{pool_id}",
    )
    rows = data.get("data", data) if isinstance(data, dict) else data
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").set_index("timestamp")
    df["apy"] = pd.to_numeric(df.get("apy", df.get("apyBase", 0)), errors="coerce").fillna(0)
    df["apyBase"] = pd.to_numeric(df.get("apyBase", 0), errors="coerce").fillna(0)
    df["apyReward"] = pd.to_numeric(df.get("apyReward", 0), errors="coerce").fillna(0)
    df["tvlUsd"] = pd.to_numeric(df.get("tvlUsd", 0), errors="coerce").fillna(0)
    return df.tail(HISTORY_DAYS)


# ── ETH price history ─────────────────────────────────────────────────────────

def get_eth_price_history(days: int = HISTORY_DAYS) -> pd.DataFrame:
    """Return daily ETH/USD price DataFrame indexed by date."""
    start_ts = int(time.time()) - days * 86400
    coin_id = f"ethereum:{WETH_ADDRESS}"
    url = (
        f"{DEFILLAMA_COINS_URL}/chart/{coin_id}"
        f"?start={start_ts}&span={days}&period=1d"
    )
    cache_key = f"eth_price_{days}d"
    try:
        data = _get(url, cache_key)
        prices = data["coins"][coin_id]["prices"]
        df = pd.DataFrame(prices)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        df = df.rename(columns={"price": "eth_price"}).set_index("timestamp")
        df.index = df.index.normalize()
        return df[["eth_price"]].sort_index().tail(days)
    except Exception as e:
        print(f"  [warn] ETH price API failed ({e}), using mock prices")
        return _mock_eth_prices(days)


# ── Named getters ─────────────────────────────────────────────────────────────

def get_uniswap_eth_usdc(pools=None) -> tuple[pd.DataFrame, dict]:
    pools = pools or get_all_pools()
    pool = find_pool(pools, "uniswap-v3", "Ethereum", "USDC")
    if pool is None:
        pool = find_pool(pools, "uniswap-v3", "Ethereum", "WETH")
    if pool is None:
        print("  [warn] Uniswap V3 ETH/USDC pool not found — using mock data")
        return _mock_pool_history("uniswap"), {}
    print(f"  Uniswap V3 pool: {pool.get('symbol')}  TVL ${pool.get('tvlUsd',0):,.0f}")
    try:
        return get_pool_history(pool["pool"]), pool
    except Exception as e:
        print(f"  [warn] {e} — using mock data")
        return _mock_pool_history("uniswap"), pool


def get_aave_usdc(pools=None) -> tuple[pd.DataFrame, dict]:
    pools = pools or get_all_pools()
    pool = find_pool(pools, "aave-v3", "Ethereum", "USDC")
    if pool is None:
        print("  [warn] Aave V3 USDC pool not found — using mock data")
        return _mock_pool_history("aave"), {}
    print(f"  Aave V3 pool: {pool.get('symbol')}  APY {pool.get('apy',0):.2f}%")
    try:
        return get_pool_history(pool["pool"]), pool
    except Exception as e:
        print(f"  [warn] {e} — using mock data")
        return _mock_pool_history("aave"), pool


def get_compound_usdc(pools=None) -> tuple[pd.DataFrame, dict]:
    pools = pools or get_all_pools()
    pool = find_pool(pools, "compound-v3", "Ethereum", "USDC")
    if pool is None:
        pool = find_pool(pools, "compound", "Ethereum", "USDC")
    if pool is None:
        print("  [warn] Compound USDC pool not found — using mock data")
        return _mock_pool_history("compound"), {}
    print(f"  Compound pool: {pool.get('symbol')}  APY {pool.get('apy',0):.2f}%")
    try:
        return get_pool_history(pool["pool"]), pool
    except Exception as e:
        print(f"  [warn] {e} — using mock data")
        return _mock_pool_history("compound"), pool


def get_yearn_usdc(pools=None) -> tuple[pd.DataFrame, dict]:
    pools = pools or get_all_pools()
    pool = find_pool(pools, "yearn-finance", "Ethereum", "USDC")
    if pool is None:
        print("  [warn] Yearn USDC vault not found — using mock data")
        return _mock_pool_history("yearn"), {}
    print(f"  Yearn vault: {pool.get('symbol')}  APY {pool.get('apy',0):.2f}%")
    try:
        return get_pool_history(pool["pool"]), pool
    except Exception as e:
        print(f"  [warn] {e} — using mock data")
        return _mock_pool_history("yearn"), pool


# ── Mock fallbacks ────────────────────────────────────────────────────────────

def _mock_eth_prices(days: int) -> pd.DataFrame:
    rng = np.random.default_rng(99)
    dates = pd.date_range(end=pd.Timestamp.utcnow().normalize(), periods=days, freq="D", tz="UTC")
    log_r = rng.normal(0.0005, 0.025, days)
    prices = 2200.0 * np.exp(np.cumsum(log_r))
    return pd.DataFrame({"eth_price": prices}, index=dates)


_MOCK_PARAMS = {
    "uniswap":  {"base": 8.5,  "vol": 0.30, "tvl": 220_000_000},
    "aave":     {"base": 4.6,  "vol": 0.10, "tvl": 800_000_000},
    "compound": {"base": 4.1,  "vol": 0.10, "tvl": 400_000_000},
    "yearn":    {"base": 5.9,  "vol": 0.15, "tvl": 120_000_000},
}


def _mock_pool_history(name: str) -> pd.DataFrame:
    p = _MOCK_PARAMS.get(name, {"base": 5.0, "vol": 0.15, "tvl": 100_000_000})
    rng = np.random.default_rng({"uniswap": 1, "aave": 2, "compound": 3, "yearn": 4}.get(name, 0))
    dates = pd.date_range(
        end=pd.Timestamp.utcnow().normalize(), periods=HISTORY_DAYS, freq="D", tz="UTC"
    )
    apy = p["base"] + np.cumsum(rng.normal(0, p["vol"], HISTORY_DAYS))
    apy = np.clip(apy, 0.5, 50.0)
    tvl = p["tvl"] * (1 + 0.05 * rng.standard_normal(HISTORY_DAYS))
    df = pd.DataFrame(
        {"apy": apy, "apyBase": apy, "apyReward": 0.0, "tvlUsd": tvl},
        index=dates,
    )
    return df
