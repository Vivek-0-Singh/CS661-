"""
Vectorized backtesting engine — implemented from scratch with pandas/numpy.

Strategy A (LP Optimizer):
    Tracks daily P&L = fee_revenue + delta_IL.
    Concentration multiplier applied when price is inside tick range.
    IL tracked as running change from position entry price.

Strategy B (Yield Arbitrage):
    Accumulates lending APY daily.
    Deducts rotation gas cost (as fraction of capital) on ROTATE days.

Benchmarks:
    • HODL ETH   — pure ETH log-return series.
    • Aave lend  — compound Aave USDC APY daily.
    • Yearn vault — compound Yearn vault APY daily.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from crypto_crush.strategies.lp_optimizer import (
    impermanent_loss, concentration_factor,
)
from crypto_crush.config import GAS_UNITS_ROTATION, INITIAL_CAPITAL
from crypto_crush.backtest.metrics import compute_metrics, equity_curve, rolling_sharpe, drawdown_series


# ── Strategy A backtest ───────────────────────────────────────────────────────

def backtest_lp(
    features: pd.DataFrame,
    signals:  pd.DataFrame,
) -> dict:
    """
    Simulate Strategy A on aligned features + signals DataFrame.

    Returns dict with daily_returns, fee_returns, il_returns, equity, metrics.
    """
    idx          = features.index.intersection(signals.index)
    feat         = features.loc[idx]
    sig_df       = signals.loc[idx]

    n            = len(idx)
    daily_ret    = np.zeros(n)
    fee_ret      = np.zeros(n)
    il_ret       = np.zeros(n)

    in_pos       = False
    entry_price  = np.nan
    P_a = P_b    = np.nan
    prev_price   = np.nan
    prev_il      = 0.0

    for i, date in enumerate(idx):
        row      = feat.loc[date]
        sig_row  = sig_df.loc[date]
        price    = float(row["eth_price"])
        daily_apy = float(row["apy"])            # pool APY %
        sig      = sig_row["signal"]

        if not in_pos:
            if sig in ("ENTER",):
                in_pos      = True
                entry_price = price
                P_a         = float(sig_row["P_a"]) if not np.isnan(sig_row["P_a"]) else price * 0.85
                P_b         = float(sig_row["P_b"]) if not np.isnan(sig_row["P_b"]) else price * 1.15
                prev_price  = price
                prev_il     = 0.0
            daily_ret[i] = 0.0
            continue

        # Rebalance: update tick range
        if sig == "REBALANCE" and not np.isnan(sig_row["P_a"]):
            entry_price = price
            P_a         = float(sig_row["P_a"])
            P_b         = float(sig_row["P_b"])
            prev_il     = 0.0

        # IL relative to entry price
        k          = price / entry_price if entry_price > 0 else 1.0
        current_il = impermanent_loss(k)          # ≤ 0
        delta_il   = current_il - prev_il          # change in IL today (usually ≤ 0)
        prev_il    = current_il

        # Fee revenue (only when price is in tick range)
        in_range = P_a <= price <= P_b
        if in_range:
            conc        = concentration_factor(price, P_a, P_b)
            daily_fee   = (daily_apy / 100.0) / 365.0 * conc
        else:
            daily_fee   = 0.0

        net_daily    = daily_fee + delta_il
        fee_ret[i]   = daily_fee
        il_ret[i]    = delta_il
        daily_ret[i] = net_daily

        prev_price = price

        if sig == "EXIT":
            in_pos = False
            entry_price = np.nan
            prev_il     = 0.0

    series = pd.Series(daily_ret, index=idx, name="lp_strategy")
    return {
        "name":         "LP Optimizer (Strategy A)",
        "daily_returns": series,
        "fee_returns":   pd.Series(fee_ret, index=idx, name="fee"),
        "il_returns":    pd.Series(il_ret,  index=idx, name="il"),
        "equity":        equity_curve(series, INITIAL_CAPITAL),
        "rolling_sharpe": rolling_sharpe(series),
        "drawdown":      drawdown_series(series),
        "metrics":       compute_metrics(series, "LP Optimizer (A)"),
    }


# ── Strategy B backtest ───────────────────────────────────────────────────────

def backtest_yield_arb(
    signals: pd.DataFrame,
    gas_usd: float,
) -> dict:
    """
    Simulate Strategy B: accumulate lending APY; deduct gas on rotation days.
    """
    n          = len(signals)
    daily_ret  = np.zeros(n)
    capital    = INITIAL_CAPITAL

    for i, (date, row) in enumerate(signals.iterrows()):
        apy    = float(row["current_apy"])        # % annual
        day_r  = (apy / 100.0) / 365.0

        if row["signal"] == "ROTATE" and i > 0:
            gas_drag  = gas_usd / capital
            daily_ret[i] = day_r - gas_drag
        else:
            daily_ret[i] = day_r

        capital *= (1.0 + daily_ret[i])

    series = pd.Series(daily_ret, index=signals.index, name="yield_arb")
    return {
        "name":          "Yield Arbitrage (Strategy B)",
        "daily_returns": series,
        "equity":        equity_curve(series, INITIAL_CAPITAL),
        "rolling_sharpe": rolling_sharpe(series),
        "drawdown":      drawdown_series(series),
        "metrics":       compute_metrics(series, "Yield Arb (B)"),
    }


# ── Benchmark: HODL ETH ───────────────────────────────────────────────────────

def backtest_hodl_eth(eth_df: pd.DataFrame) -> dict:
    eth = eth_df["eth_price"].sort_index()
    rets = eth.pct_change().fillna(0.0).rename("hodl_eth")
    return {
        "name":          "HODL ETH",
        "daily_returns": rets,
        "equity":        equity_curve(rets, INITIAL_CAPITAL),
        "rolling_sharpe": rolling_sharpe(rets),
        "drawdown":      drawdown_series(rets),
        "metrics":       compute_metrics(rets, "HODL ETH"),
    }


# ── Benchmark: Aave lending ───────────────────────────────────────────────────

def backtest_aave_lend(aave_df: pd.DataFrame) -> dict:
    apy  = aave_df["apy"].copy()
    apy.index = apy.index.normalize()
    rets = (apy / 100.0 / 365.0).rename("aave_lend")
    return {
        "name":          "Aave Stable Lending",
        "daily_returns": rets,
        "equity":        equity_curve(rets, INITIAL_CAPITAL),
        "rolling_sharpe": rolling_sharpe(rets),
        "drawdown":      drawdown_series(rets),
        "metrics":       compute_metrics(rets, "Aave Stable Lend"),
    }


# ── Benchmark: Yearn vault ────────────────────────────────────────────────────

def backtest_yearn(yearn_df: pd.DataFrame) -> dict:
    apy  = yearn_df["apy"].copy()
    apy.index = apy.index.normalize()
    rets = (apy / 100.0 / 365.0).rename("yearn")
    return {
        "name":          "Yearn USDC Vault",
        "daily_returns": rets,
        "equity":        equity_curve(rets, INITIAL_CAPITAL),
        "rolling_sharpe": rolling_sharpe(rets),
        "drawdown":      drawdown_series(rets),
        "metrics":       compute_metrics(rets, "Yearn USDC"),
    }


# ── Master runner ─────────────────────────────────────────────────────────────

def run_all(
    lp_result:   dict,
    arb_result:  dict,
    eth_df:      pd.DataFrame,
    aave_df:     pd.DataFrame,
    yearn_df:    pd.DataFrame,
    gas_usd:     float,
) -> dict:
    """
    Run both strategies + all benchmarks; return consolidated results dict.
    """
    print("\n[Backtest] Running Strategy A …")
    strat_a = backtest_lp(lp_result["features"], lp_result["signals"])

    print("[Backtest] Running Strategy B …")
    strat_b = backtest_yield_arb(arb_result["signals"], gas_usd)

    print("[Backtest] Running benchmarks …")
    bm_eth   = backtest_hodl_eth(eth_df)
    bm_aave  = backtest_aave_lend(aave_df)
    bm_yearn = backtest_yearn(yearn_df)

    results = {
        "strategy_a": strat_a,
        "strategy_b": strat_b,
        "hodl_eth":   bm_eth,
        "aave_lend":  bm_aave,
        "yearn":      bm_yearn,
        "lp_signals": lp_result["signals"],
        "arb_signals": arb_result["signals"],
    }

    # Print summary table
    print("\n" + "=" * 65)
    print(f"{'Strategy':<28} {'Ann Ret':>8} {'Ann Vol':>8} {'Sharpe':>7} {'MaxDD':>8}")
    print("=" * 65)
    for key in ["strategy_a", "strategy_b", "hodl_eth", "aave_lend", "yearn"]:
        m = results[key]["metrics"]
        print(
            f"{m['name']:<28} "
            f"{m['ann_return']*100:>7.2f}% "
            f"{m['ann_vol']*100:>7.2f}% "
            f"{m['sharpe']:>7.2f} "
            f"{m['max_drawdown']*100:>7.2f}%"
        )
    print("=" * 65)

    return results
