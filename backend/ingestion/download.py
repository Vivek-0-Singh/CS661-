"""Download Binance monthly 1m klines from data.binance.vision into DuckDB.

Usage:
    python -m ingestion.download --start 2024-01 --end 2024-03 --symbols BTC ETH
    python -m ingestion.download --start 2020-01 --end 2024-12          # all 5 assets

No API key / auth required. Months that don't exist yet (e.g. SOL before its
listing) are skipped gracefully.
"""
from __future__ import annotations

import argparse
import io
import sys
import zipfile
from datetime import date

import duckdb
import pandas as pd
import requests

from app.config import ASSETS, DB_PATH, SYMBOLS, VISION_BASE

# Raw Binance kline CSV columns (older monthly files ship without a header).
_RAW_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "count",
    "taker_buy_volume", "taker_buy_quote_volume", "ignore",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS klines_1m (
    symbol       VARCHAR NOT NULL,
    ts           TIMESTAMP NOT NULL,
    open         DOUBLE,
    high         DOUBLE,
    low          DOUBLE,
    close        DOUBLE,
    volume       DOUBLE,
    quote_volume DOUBLE,
    trades       BIGINT,
    PRIMARY KEY (symbol, ts)
);
"""


def _month_range(start: str, end: str) -> list[str]:
    """Inclusive list of 'YYYY-MM' strings between start and end."""
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out: list[str] = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _parse_ts(series: pd.Series) -> pd.Series:
    """Convert Binance open_time to UTC-naive datetime, auto-detecting the unit.

    Historical files use milliseconds; some 2025+ files switched to microseconds.
    Detect by magnitude of the first value.
    """
    sample = float(series.iloc[0])
    unit = "us" if sample > 1e14 else "ms"
    return pd.to_datetime(series.astype("int64"), unit=unit)


def _read_csv_from_zip(content: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        raw = zf.read(zf.namelist()[0])
    has_header = raw[:9].lower().startswith(b"open_time")
    return pd.read_csv(
        io.BytesIO(raw),
        header=0 if has_header else None,
        names=None if has_header else _RAW_COLS,
    )


def _fetch_month(symbol: str, pair: str, ym: str, session: requests.Session) -> pd.DataFrame | None:
    url = f"{VISION_BASE}/{pair}/1m/{pair}-1m-{ym}.zip"
    resp = session.get(url, timeout=60)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()

    df = _read_csv_from_zip(resp.content)
    df = df[["open_time", "open", "high", "low", "close", "volume", "quote_volume", "count"]].copy()
    df["ts"] = _parse_ts(df["open_time"])
    df.insert(0, "symbol", symbol)
    df = df.drop(columns=["open_time"]).rename(columns={"count": "trades"})
    return df[["symbol", "ts", "open", "high", "low", "close", "volume", "quote_volume", "trades"]]


def ingest(symbols: list[str], start: str, end: str) -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute(SCHEMA)
    session = requests.Session()

    months = _month_range(start, end)
    total_rows = 0
    for symbol in symbols:
        pair = ASSETS[symbol]
        for ym in months:
            try:
                df = _fetch_month(symbol, pair, ym, session)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {symbol} {ym}: {exc}", file=sys.stderr)
                continue
            if df is None or df.empty:
                print(f"  - {symbol} {ym}: not available, skipped")
                continue
            con.register("_incoming", df)
            con.execute(
                "INSERT INTO klines_1m "
                "SELECT * FROM _incoming "
                "WHERE (symbol, ts) NOT IN (SELECT symbol, ts FROM klines_1m)"
            )
            con.unregister("_incoming")
            total_rows += len(df)
            print(f"  + {symbol} {ym}: {len(df):>6} rows")

    n = con.execute("SELECT count(*) FROM klines_1m").fetchone()[0]
    con.close()
    print(f"\nDone. Ingested {total_rows} rows this run; {n} total in {DB_PATH.name}.")


def main() -> None:
    p = argparse.ArgumentParser(description="Download Binance 1m klines into DuckDB.")
    p.add_argument("--start", required=True, help="start month, YYYY-MM")
    p.add_argument("--end", default=date.today().strftime("%Y-%m"), help="end month, YYYY-MM")
    p.add_argument("--symbols", nargs="*", default=SYMBOLS, help=f"subset of {SYMBOLS}")
    args = p.parse_args()

    bad = [s for s in args.symbols if s not in ASSETS]
    if bad:
        p.error(f"unknown symbols {bad}; choose from {SYMBOLS}")

    print(f"Ingesting {args.symbols} for {args.start}..{args.end}")
    ingest(args.symbols, args.start, args.end)


if __name__ == "__main__":
    main()
