"""DuckDB access layer.

The database is built by ``ingestion.download`` and read read-only by the API.
Access goes through per-call cursors guarded by a lock so FastAPI's threadpool
can share one connection safely.
"""
from __future__ import annotations

import threading
from datetime import datetime

import duckdb
import pandas as pd

from .config import ASSETS, DB_PATH, RESOLUTIONS

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None


class DataUnavailable(RuntimeError):
    """Raised when the DuckDB file has not been built yet."""


def get_con() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        if not DB_PATH.exists():
            raise DataUnavailable(
                f"{DB_PATH} not found — run `python -m ingestion.download` first."
            )
        _con = duckdb.connect(str(DB_PATH), read_only=True)
    return _con


def _query(sql: str, params: list | None = None) -> pd.DataFrame:
    with _lock:
        cur = get_con().cursor()
        return cur.execute(sql, params or []).df()


# --- metadata --------------------------------------------------------------
def coverage() -> list[dict]:
    """Per-symbol time coverage and row counts."""
    df = _query(
        "SELECT symbol, min(ts) AS start, max(ts) AS end, count(*) AS rows "
        "FROM klines_1m GROUP BY symbol ORDER BY symbol"
    )
    df["start"] = df["start"].astype(str)
    df["end"] = df["end"].astype(str)
    return df.to_dict("records")


def pick_resolution(start: datetime, end: datetime) -> str:
    """Auto-select candle resolution from the selected window length."""
    span_days = (end - start).total_seconds() / 86400
    if span_days <= 3:
        return "1m"
    if span_days <= 60:
        return "1h"
    return "1d"


# --- OHLCV -----------------------------------------------------------------
def ohlcv(symbol: str, start: datetime, end: datetime, resolution: str) -> pd.DataFrame:
    if symbol not in ASSETS:
        raise ValueError(f"unknown symbol {symbol}")
    if resolution not in RESOLUTIONS:
        raise ValueError(f"unknown resolution {resolution}")

    if resolution == "1m":
        sql = (
            "SELECT ts, open, high, low, close, volume "
            "FROM klines_1m WHERE symbol = ? AND ts BETWEEN ? AND ? ORDER BY ts"
        )
        return _query(sql, [symbol, start, end])

    interval = RESOLUTIONS[resolution]  # whitelisted -> safe to inline
    sql = f"""
        SELECT time_bucket(INTERVAL '{interval}', ts) AS ts,
               arg_min(open, ts)  AS open,
               max(high)          AS high,
               min(low)           AS low,
               arg_max(close, ts) AS close,
               sum(volume)        AS volume
        FROM klines_1m
        WHERE symbol = ? AND ts BETWEEN ? AND ?
        GROUP BY 1 ORDER BY 1
    """
    return _query(sql, [symbol, start, end])


def closes(symbols: list[str], start: datetime, end: datetime, resolution: str) -> pd.DataFrame:
    """Wide frame of bucketed close prices: index=ts, one column per symbol."""
    interval = RESOLUTIONS[resolution]
    frames = []
    for sym in symbols:
        df = _query(
            f"""SELECT time_bucket(INTERVAL '{interval}', ts) AS ts,
                       arg_max(close, ts) AS close
                FROM klines_1m
                WHERE symbol = ? AND ts BETWEEN ? AND ?
                GROUP BY 1 ORDER BY 1""",
            [sym, start, end],
        ).set_index("ts")["close"].rename(sym)
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1).sort_index()


def full_range(symbol: str) -> tuple[datetime, datetime] | None:
    df = _query(
        "SELECT min(ts) AS start, max(ts) AS end FROM klines_1m WHERE symbol = ?",
        [symbol],
    )
    if df.empty or pd.isna(df.iloc[0]["start"]):
        return None
    return df.iloc[0]["start"].to_pydatetime(), df.iloc[0]["end"].to_pydatetime()
