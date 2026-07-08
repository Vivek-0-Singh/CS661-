"""Statistical engine: volatility / risk, correlation, and pattern back-testing.

All functions take plain pandas objects (built by ``store``) so they are easy to
unit-test in isolation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps

# Trading periods per year (crypto trades 24/7/365).
PERIODS_PER_YEAR = {"1m": 525_600, "1h": 8_760, "1d": 365}
_ROLL_WIN = {"1m": 60, "1h": 24, "1d": 30}
_DROP_THRESHOLDS = [0.05, 0.10, 0.15, 0.20]


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1)).dropna()


def _downsample(df: pd.DataFrame, max_points: int = 600) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    step = int(np.ceil(len(df) / max_points))
    return df.iloc[::step]


# --- Volatility / risk -----------------------------------------------------
def _scenario_samples(mu: float, sigma: float, kind: str, n: int, rng) -> np.ndarray:
    """Draw single-period return samples for a market scenario.

    normal: Gaussian at the empirical mean/vol.
    stress: fatter-tailed Student-t (df=5) with ~1.6x volatility.
    crash:  very heavy-tailed Student-t (df=3), ~2.5x volatility, negative drift.
    """
    if kind == "normal":
        return rng.normal(mu, sigma, n)
    if kind == "stress":
        df = 5
        scale = (sigma * 1.6) / np.sqrt(df / (df - 2))
        return mu + scale * rng.standard_t(df, n)
    if kind == "crash":
        df = 3
        scale = (sigma * 2.5) / np.sqrt(df / (df - 2))
        return (mu - 0.5 * sigma) + scale * rng.standard_t(df, n)
    raise ValueError(f"unknown scenario {kind}")


def _scenario_metrics(samples: np.ndarray) -> dict:
    q5, q1 = np.percentile(samples, [5, 1])
    tail = samples[samples <= q5]
    return {
        "var95": float(-q5),
        "var99": float(-q1),
        "cvar95": float(-tail.mean()) if tail.size else float(-q5),
        "drop_probs": {
            f"{t:.2f}": float(np.mean(samples <= -t)) for t in _DROP_THRESHOLDS
        },
    }


def volatility_report(close: pd.Series, resolution: str) -> dict:
    ret = log_returns(close)
    if len(ret) < 5:
        raise ValueError("not enough data in window for a volatility report")

    ppy = PERIODS_PER_YEAR[resolution]
    win = min(_ROLL_WIN[resolution], max(2, len(ret) // 3))
    roll = (ret.rolling(win).std() * np.sqrt(ppy)).dropna()
    roll_df = _downsample(roll.reset_index())
    roll_df.columns = ["ts", "vol"]

    mu, sigma = float(ret.mean()), float(ret.std())
    counts, edges = np.histogram(ret.values, bins=60)

    rng = np.random.default_rng(42)
    n = 200_000
    scenarios = {
        k: _scenario_metrics(_scenario_samples(mu, sigma, k, n, rng))
        for k in ("normal", "stress", "crash")
    }

    return {
        "resolution": resolution,
        "annualized_vol": float(sigma * np.sqrt(ppy)),
        "rolling": [
            {"ts": str(t), "vol": float(v)}
            for t, v in zip(roll_df["ts"], roll_df["vol"])
        ],
        "distribution": {
            "mean": mu,
            "std": sigma,
            "skew": float(sps.skew(ret.values)),
            "kurtosis": float(sps.kurtosis(ret.values)),  # excess kurtosis
            "n": int(len(ret)),
        },
        "histogram": {
            "bins": [float(x) for x in edges],
            "counts": [int(c) for c in counts],
        },
        "scenarios": scenarios,
    }


# --- Correlation -----------------------------------------------------------
def correlation_matrix(close_wide: pd.DataFrame) -> dict:
    ret = np.log(close_wide / close_wide.shift(1))
    ret = ret.dropna(how="all")
    corr = ret.corr(min_periods=3)
    labels = list(corr.columns)
    matrix = [[None if pd.isna(v) else float(v) for v in row] for row in corr.values]
    return {"labels": labels, "matrix": matrix, "n": int(len(ret))}


def rolling_correlation(
    close_a: pd.Series, close_b: pd.Series, window: int
) -> dict:
    joined = pd.concat(
        [log_returns(close_a).rename("a"), log_returns(close_b).rename("b")], axis=1
    ).dropna()
    if len(joined) < window:
        window = max(3, len(joined) // 3)
    roll = joined["a"].rolling(window).corr(joined["b"]).dropna()
    roll_df = _downsample(roll.reset_index())
    roll_df.columns = ["ts", "corr"]
    overall = float(joined["a"].corr(joined["b"])) if len(joined) > 2 else None
    return {
        "window": window,
        "overall": overall,
        "series": [
            {"ts": str(t), "corr": float(c)}
            for t, c in zip(roll_df["ts"], roll_df["corr"])
        ],
    }


# --- Pattern hypothesis tester --------------------------------------------
def pattern_scan(
    close: pd.Series,
    direction: str,
    threshold: float,
    lookback: int,
    horizon: int,
) -> dict:
    """Find every past instance of a trigger and track forward price paths.

    direction: 'drop' (move <= -threshold) or 'spike' (move >= +threshold),
    measured as the return over ``lookback`` periods. For each event, cumulative
    forward returns are tracked over ``horizon`` periods.
    """
    if direction not in ("drop", "spike"):
        raise ValueError("direction must be 'drop' or 'spike'")

    c = close.dropna()
    values = c.values.astype(float)
    idx = c.index
    n = len(values)
    if n < lookback + horizon + 1:
        raise ValueError("not enough data to scan this pattern")

    base_ret = values[lookback:] / values[:-lookback] - 1.0  # aligned to position `lookback+i`
    trigger = base_ret <= -threshold if direction == "drop" else base_ret >= threshold

    # Absolute positions of trigger bars, keeping room for `horizon` ahead.
    positions = np.nonzero(trigger)[0] + lookback
    positions = positions[positions + horizon < n]
    if positions.size == 0:
        return {
            "n_events": 0, "horizon": horizon,
            "bands": [], "terminal": None, "sample_events": [],
        }

    # forward cumulative returns matrix: (n_events x horizon)
    paths = np.empty((positions.size, horizon))
    for k in range(1, horizon + 1):
        paths[:, k - 1] = values[positions + k] / values[positions] - 1.0

    pct = np.percentile(paths, [10, 25, 50, 75, 90], axis=0)
    bands = [
        {
            "step": k + 1,
            "mean": float(paths[:, k].mean()),
            "p10": float(pct[0, k]), "p25": float(pct[1, k]),
            "p50": float(pct[2, k]), "p75": float(pct[3, k]),
            "p90": float(pct[4, k]),
        }
        for k in range(horizon)
    ]

    terminal = paths[:, -1]
    terminal_stats = {
        "mean": float(terminal.mean()),
        "median": float(np.median(terminal)),
        "win_rate": float(np.mean(terminal > 0)),
        "p10": float(np.percentile(terminal, 10)),
        "p90": float(np.percentile(terminal, 90)),
        "best": float(terminal.max()),
        "worst": float(terminal.min()),
    }

    # A capped sample of event timestamps for the frontend to mark.
    ev = positions if positions.size <= 500 else positions[:: positions.size // 500]
    sample_events = [str(idx[p]) for p in ev]

    return {
        "n_events": int(positions.size),
        "horizon": horizon,
        "bands": bands,
        "terminal": terminal_stats,
        "sample_events": sample_events,
    }
