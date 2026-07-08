"""
Strategy A — Uniswap V3 Concentrated Liquidity Optimizer.

Approach:
  • Fetch ETH/USDC pool APY + TVL history from DefiLlama.
  • Fetch ETH price history from DefiLlama coins API.
  • Engineer daily features: fee APR, vol/TVL ratio, rolling realized volatility.
  • Optimize tick range [P_a, P_b] via scipy grid-search to maximise:
        E[fee_revenue * concentration] − E[IL_cost]
    using a log-normal price model fitted to rolling realized vol.
  • Signal: ENTER when 30-day vol is below its 40th percentile.
            EXIT  when 5-day vol spikes above 1.8× its 30-day average.
  • Rebalance (re-optimise range) every LP_REBALANCE_DAYS.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import norm

from crypto_crush.config import (
    LP_FEE_TIER, LP_MIN_RANGE_WIDTH, LP_MAX_RANGE_WIDTH,
    LP_VOL_ENTRY_PCTILE, LP_VOL_EXIT_MULT, LP_REBALANCE_DAYS,
    HISTORY_DAYS,
)


# ── Uniswap V3 math helpers ───────────────────────────────────────────────────

def concentration_factor(P: float, P_a: float, P_b: float) -> float:
    """
    Capital efficiency multiplier of a V3 concentrated position vs full range.
    Derived from liquidity formula: L = amount / (1/sqrt(P_a) - 1/sqrt(P_b)).
    Approximation valid when P is well inside [P_a, P_b].
    """
    if P_a >= P_b or P <= 0:
        return 1.0
    sp, spa, spb = np.sqrt(P), np.sqrt(P_a), np.sqrt(P_b)
    numerator   = sp * spb - sp * spa          # portion of range above P
    denominator = sp - spa                      # full range denominator term
    if denominator <= 0:
        return 1.0
    return max(1.0, (spb - spa) / (sp - spa + 1e-12) * 0.5)


def impermanent_loss(k: float) -> float:
    """
    Standard IL formula: IL = 2√k / (1+k) − 1  where k = P_new / P_old.
    Returns a negative number (loss).
    """
    if k <= 0:
        return -1.0
    return 2.0 * np.sqrt(k) / (1.0 + k) - 1.0


def prob_in_range(P: float, P_a: float, P_b: float, annual_vol: float, horizon_days: int = 1) -> float:
    """
    P( P_a ≤ P_T ≤ P_b ) under GBM with annual vol σ over horizon T days.
    Uses log-normal CDF difference.
    """
    if annual_vol <= 0 or P_a >= P_b:
        return 1.0
    sigma_sqrt_t = annual_vol * np.sqrt(horizon_days / 365.0)
    lo = (np.log(P_a / P) + 0.5 * sigma_sqrt_t**2) / sigma_sqrt_t
    hi = (np.log(P_b / P) + 0.5 * sigma_sqrt_t**2) / sigma_sqrt_t
    return float(norm.cdf(hi) - norm.cdf(lo))


# ── Range optimiser ───────────────────────────────────────────────────────────

def optimise_range(
    current_price: float,
    annual_vol: float,
    pool_base_apy: float,
) -> tuple[float, float, float, float]:
    """
    Grid-search over symmetric range half-width r ∈ [MIN, MAX] to maximise:
        net_apy = fee_apy_concentrated * p_in_range − il_cost_annualised

    Returns (P_a, P_b, optimal_r, expected_net_apy).
    """
    def neg_net_apy(r: float) -> float:
        P_a = current_price * (1 - r)
        P_b = current_price * (1 + r)

        conc  = concentration_factor(current_price, P_a, P_b)
        p_in  = prob_in_range(current_price, P_a, P_b, annual_vol, horizon_days=LP_REBALANCE_DAYS)

        # Fee revenue only earned when in range
        gross_fee_apy = pool_base_apy * conc * p_in

        # Expected IL at the range boundary (worst case when forced out)
        k_hi = 1.0 + r
        k_lo = 1.0 / (1.0 - r + 1e-9)
        avg_il = (abs(impermanent_loss(k_hi)) + abs(impermanent_loss(k_lo))) / 2.0
        # Weight IL cost by probability of leaving range (annualised approximation)
        p_out_annual = max(0.0, 1.0 - prob_in_range(current_price, P_a, P_b, annual_vol, 365))
        il_cost_apy = avg_il * 100.0 * p_out_annual

        return -(gross_fee_apy - il_cost_apy)

    res = minimize_scalar(
        neg_net_apy,
        bounds=(LP_MIN_RANGE_WIDTH, LP_MAX_RANGE_WIDTH),
        method="bounded",
    )
    r = float(res.x)
    P_a = current_price * (1 - r)
    P_b = current_price * (1 + r)
    net_apy = float(-res.fun)
    return P_a, P_b, r, net_apy


# ── Feature engineering ───────────────────────────────────────────────────────

def build_features(pool_df: pd.DataFrame, eth_df: pd.DataFrame) -> pd.DataFrame:
    """Merge pool and price data; compute rolling vol and regime features."""
    # Align on daily UTC dates
    pool = pool_df.copy()
    pool.index = pool.index.normalize()
    eth  = eth_df.copy()
    eth.index = eth.index.normalize()

    df = pool.join(eth, how="inner")
    df = df.sort_index()

    # Log returns of ETH price
    df["log_ret"] = np.log(df["eth_price"] / df["eth_price"].shift(1))

    # Rolling realized vol (annualised)
    df["vol_30d"] = df["log_ret"].rolling(30).std() * np.sqrt(252)
    df["vol_5d"]  = df["log_ret"].rolling(5).std()  * np.sqrt(252)

    # Vol regime signals
    vol_pctile = df["vol_30d"].expanding().quantile(LP_VOL_ENTRY_PCTILE / 100)
    df["low_vol_regime"] = df["vol_30d"] < vol_pctile
    df["vol_spike"]      = df["vol_5d"]  > (LP_VOL_EXIT_MULT * df["vol_30d"])

    # Volume / TVL proxy (volume not directly in DefiLlama pool history, proxy via apy change)
    df["apy_change"] = df["apy"].pct_change()

    return df.dropna(subset=["vol_30d"])


# ── Signal generation ─────────────────────────────────────────────────────────

def generate_signals(features: pd.DataFrame) -> pd.DataFrame:
    """
    Returns DataFrame with columns: signal, P_a, P_b, opt_range, net_apy_est.
    signal ∈ {HOLD, ENTER, EXIT}.
    """
    records = []
    in_position = False
    days_since_rebalance = 0

    for date, row in features.iterrows():
        sig = "HOLD"
        P_a, P_b, opt_r, net_est = np.nan, np.nan, np.nan, np.nan

        if not in_position:
            if row["low_vol_regime"] and row["vol_30d"] > 0:
                sig = "ENTER"
                in_position = True
                days_since_rebalance = 0
                P_a, P_b, opt_r, net_est = optimise_range(
                    row["eth_price"], row["vol_30d"], row["apy"]
                )
        else:
            days_since_rebalance += 1
            if row["vol_spike"]:
                sig = "EXIT"
                in_position = False
            elif days_since_rebalance >= LP_REBALANCE_DAYS:
                sig = "REBALANCE"
                days_since_rebalance = 0
                P_a, P_b, opt_r, net_est = optimise_range(
                    row["eth_price"], row["vol_30d"], row["apy"]
                )

        records.append({
            "date":    date,
            "signal":  sig,
            "P_a":     P_a,
            "P_b":     P_b,
            "opt_r":   opt_r,
            "net_apy_est": net_est,
        })

    return pd.DataFrame(records).set_index("date")


# ── Public runner ─────────────────────────────────────────────────────────────

def run(pool_df: pd.DataFrame, eth_df: pd.DataFrame) -> dict:
    """
    Full Strategy A pipeline.
    Returns dict with keys: features, signals, name.
    """
    print("\n[Strategy A] Building features …")
    features = build_features(pool_df, eth_df)
    print(f"  {len(features)} trading days, vol range "
          f"{features['vol_30d'].min()*100:.1f}%–{features['vol_30d'].max()*100:.1f}%")

    print("[Strategy A] Generating entry/exit signals …")
    signals = generate_signals(features)
    n_enter = (signals["signal"] == "ENTER").sum()
    n_exit  = (signals["signal"] == "EXIT").sum()
    print(f"  {n_enter} entries, {n_exit} exits over {len(signals)} days")

    return {"features": features, "signals": signals, "name": "LP Optimizer (Strategy A)"}
