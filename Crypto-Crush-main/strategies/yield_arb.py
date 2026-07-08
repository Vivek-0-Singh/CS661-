"""
Strategy B — Cross-Protocol Yield Arbitrage (Aave V3 vs Compound V3).

Approach:
  • Fetch daily USDC supply APY from Aave V3 and Compound V3 via DefiLlama.
  • Fetch live gas price from Etherscan; compute USD cost to rotate $100k capital.
  • Identify when APY differential > ARB_THRESHOLD_PCT after netting gas cost.
  • Enforce ARB_MIN_HOLD_DAYS between rotations to prevent gas-churning.
  • Model rotation cost as: gas_usd / capital  (expressed as annualised APY drag).
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from crypto_crush.config import (
    ARB_THRESHOLD_PCT, ARB_MIN_HOLD_DAYS,
    GAS_UNITS_ROTATION, INITIAL_CAPITAL, HISTORY_DAYS,
)


# ── Gas cost helpers ──────────────────────────────────────────────────────────

def rotation_cost_apy(gas_usd: float, capital: float = INITIAL_CAPITAL) -> float:
    """
    Annualised APY drag of a single rotation.
    Assumes capital stays at new protocol for at least ARB_MIN_HOLD_DAYS.
    """
    daily_drag = gas_usd / capital          # fraction of capital lost
    annual_drag = daily_drag * (365.0 / ARB_MIN_HOLD_DAYS)
    return annual_drag * 100.0              # as percentage


# ── Feature engineering ───────────────────────────────────────────────────────

def build_features(
    aave_df: pd.DataFrame,
    comp_df: pd.DataFrame,
    gas_usd: float,
) -> pd.DataFrame:
    """
    Merge Aave and Compound daily APY series; compute differential and net spread.
    """
    aave = aave_df[["apy"]].rename(columns={"apy": "aave_apy"}).copy()
    comp = comp_df[["apy"]].rename(columns={"apy": "comp_apy"}).copy()

    aave.index = aave.index.normalize()
    comp.index = comp.index.normalize()

    df = aave.join(comp, how="inner").sort_index().tail(HISTORY_DAYS)

    # Rolling 7-day smoothed APY (reduces noise-driven rotations)
    df["aave_apy_smooth"] = df["aave_apy"].rolling(3, min_periods=1).mean()
    df["comp_apy_smooth"] = df["comp_apy"].rolling(3, min_periods=1).mean()

    df["differential"] = df["aave_apy_smooth"] - df["comp_apy_smooth"]
    df["best_protocol"] = np.where(df["aave_apy_smooth"] >= df["comp_apy_smooth"], "aave", "compound")
    df["best_apy"]      = np.maximum(df["aave_apy_smooth"], df["comp_apy_smooth"])

    cost_apy = rotation_cost_apy(gas_usd)
    df["net_spread"] = df["differential"].abs() - cost_apy   # spread after gas

    return df


# ── Signal generation ─────────────────────────────────────────────────────────

def generate_signals(features: pd.DataFrame) -> pd.DataFrame:
    """
    Returns DataFrame with columns: signal, protocol, current_apy, gas_apy_drag.
    signal ∈ {HOLD, ROTATE}.
    """
    records = []
    current_protocol = None
    days_in_protocol = 0

    for date, row in features.iterrows():
        sig = "HOLD"
        target = row["best_protocol"]

        if current_protocol is None:
            # First day — deploy to best protocol immediately
            current_protocol = target
            sig = "ROTATE"
            days_in_protocol = 0
        elif (
            target != current_protocol
            and row["net_spread"] > ARB_THRESHOLD_PCT
            and days_in_protocol >= ARB_MIN_HOLD_DAYS
        ):
            sig = "ROTATE"
            current_protocol = target
            days_in_protocol = 0

        days_in_protocol += 1
        current_apy = (
            row["aave_apy"] if current_protocol == "aave" else row["comp_apy"]
        )

        records.append({
            "date":         date,
            "signal":       sig,
            "protocol":     current_protocol,
            "current_apy":  current_apy,
            "aave_apy":     row["aave_apy"],
            "comp_apy":     row["comp_apy"],
            "differential": row["differential"],
            "net_spread":   row["net_spread"],
        })

    return pd.DataFrame(records).set_index("date")


# ── Public runner ─────────────────────────────────────────────────────────────

def run(
    aave_df: pd.DataFrame,
    comp_df: pd.DataFrame,
    gas_usd: float,
) -> dict:
    """
    Full Strategy B pipeline.
    Returns dict with keys: features, signals, name.
    """
    print("\n[Strategy B] Building yield differential features …")
    features = build_features(aave_df, comp_df, gas_usd)

    aave_mean = features["aave_apy"].mean()
    comp_mean = features["comp_apy"].mean()
    print(f"  Avg Aave APY: {aave_mean:.2f}%   Avg Compound APY: {comp_mean:.2f}%")
    print(f"  Gas cost per rotation: ${gas_usd:.2f}  "
          f"(≈ {rotation_cost_apy(gas_usd):.3f}% APY drag)")

    print("[Strategy B] Generating rotation signals …")
    signals = generate_signals(features)
    n_rotations = (signals["signal"] == "ROTATE").sum()
    print(f"  {n_rotations} rotations over {len(signals)} days")

    return {"features": features, "signals": signals, "name": "Yield Arbitrage (Strategy B)"}
