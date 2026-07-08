"""Vectorized performance metric computation — no external backtesting libraries."""
from __future__ import annotations
import numpy as np
import pandas as pd
from crypto_crush.config import RISK_FREE_RATE


def compute_metrics(daily_returns: pd.Series, name: str = "") -> dict:
    """
    Compute full suite of risk/return metrics from a daily returns series.

    Parameters
    ----------
    daily_returns : pd.Series
        Arithmetic daily returns (e.g., 0.01 = 1%).

    Returns
    -------
    dict with keys: name, n_days, total_return, ann_return, ann_vol,
                    sharpe, sortino, max_drawdown, calmar.
    """
    r = daily_returns.dropna().values
    n = len(r)
    if n == 0:
        return {k: np.nan for k in [
            "name","n_days","total_return","ann_return","ann_vol",
            "sharpe","sortino","max_drawdown","calmar"
        ]}

    # Cumulative & annualised return
    cum_ret  = float(np.prod(1.0 + r) - 1.0)
    ann_ret  = float((1.0 + cum_ret) ** (252.0 / n) - 1.0)

    # Annualised volatility
    ann_vol  = float(np.std(r, ddof=1) * np.sqrt(252))

    # Sharpe (using configured risk-free rate)
    rf_daily = RISK_FREE_RATE / 252.0
    excess   = r - rf_daily
    sharpe   = float(np.mean(excess) / (np.std(excess, ddof=1) + 1e-12) * np.sqrt(252))

    # Sortino (downside vol only)
    downside = excess[excess < 0]
    down_vol = float(np.std(downside, ddof=1) * np.sqrt(252)) if len(downside) > 1 else 1e-12
    sortino  = float((ann_ret - RISK_FREE_RATE) / (down_vol + 1e-12))

    # Max drawdown
    equity = np.cumprod(1.0 + r)
    peak   = np.maximum.accumulate(equity)
    dd     = (equity - peak) / (peak + 1e-12)
    max_dd = float(np.min(dd))

    # Calmar
    calmar = float(ann_ret / (abs(max_dd) + 1e-12))

    return {
        "name":         name,
        "n_days":       n,
        "total_return": cum_ret,
        "ann_return":   ann_ret,
        "ann_vol":      ann_vol,
        "sharpe":       sharpe,
        "sortino":      sortino,
        "max_drawdown": max_dd,
        "calmar":       calmar,
    }


def equity_curve(daily_returns: pd.Series, initial: float = 1.0) -> pd.Series:
    """Convert daily returns to a cumulative equity curve."""
    return (1.0 + daily_returns.fillna(0.0)).cumprod() * initial


def rolling_sharpe(daily_returns: pd.Series, window: int = 30) -> pd.Series:
    """30-day rolling annualised Sharpe ratio."""
    rf = RISK_FREE_RATE / 252.0
    exc = daily_returns - rf
    roll_mean = exc.rolling(window).mean()
    roll_std  = exc.rolling(window).std(ddof=1)
    return (roll_mean / (roll_std + 1e-12)) * np.sqrt(252)


def drawdown_series(daily_returns: pd.Series) -> pd.Series:
    """Drawdown time series (0 to -1)."""
    eq   = equity_curve(daily_returns)
    peak = eq.cummax()
    return (eq - peak) / (peak + 1e-12)
