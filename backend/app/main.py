"""CryptoLens REST API (FastAPI).

Endpoints (all under /api):
    GET /health
    GET /meta                         coverage + symbols + suggested default window
    GET /ohlcv                        candlesticks at a resolution (auto by default)
    GET /volatility                   risk report + normal/stress/crash scenarios
    GET /correlation                  5x5 correlation matrix for a window
    GET /correlation/pair             rolling correlation for one pair
    GET /patterns                     what-if pattern back-test
    GET /depth                        reconstructed historical order book
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import stats, store
from .config import ASSETS, CORS_ORIGINS, RESOLUTIONS, SYMBOLS
from .depth import reconstruct_depth

app = FastAPI(title="CryptoLens API", version="0.1.0")

_origins = ["*"] if CORS_ORIGINS.strip() == "*" else [o.strip() for o in CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_resolution(resolution: str, start: datetime, end: datetime) -> str:
    if resolution == "auto":
        return store.pick_resolution(start, end)
    if resolution not in RESOLUTIONS:
        raise HTTPException(400, f"resolution must be 'auto' or one of {list(RESOLUTIONS)}")
    return resolution


def _guard_data():
    try:
        return store.coverage()
    except store.DataUnavailable as exc:
        raise HTTPException(503, str(exc))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    cov = _guard_data()
    # Suggested default window: last 6 months of whatever data exists.
    ends = [datetime.fromisoformat(c["end"]) for c in cov if c["rows"]]
    starts = [datetime.fromisoformat(c["start"]) for c in cov if c["rows"]]
    default = None
    if ends and starts:
        end = max(ends)
        start = max(min(starts), end - timedelta(days=180))
        default = {"start": start.isoformat(), "end": end.isoformat()}
    return {
        "symbols": SYMBOLS,
        "pairs": ASSETS,
        "resolutions": list(RESOLUTIONS),
        "coverage": cov,
        "default_window": default,
    }


@app.get("/api/ohlcv")
def ohlcv(
    symbol: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    resolution: str = Query("auto"),
):
    if symbol not in ASSETS:
        raise HTTPException(400, f"unknown symbol {symbol}; choose from {SYMBOLS}")
    res = _resolve_resolution(resolution, start, end)
    try:
        df = store.ohlcv(symbol, start, end, res)
    except store.DataUnavailable as exc:
        raise HTTPException(503, str(exc))
    return {
        "symbol": symbol,
        "resolution": res,
        "candles": [
            {
                "ts": str(r.ts), "open": r.open, "high": r.high,
                "low": r.low, "close": r.close, "volume": r.volume,
            }
            for r in df.itertuples()
        ],
    }


@app.get("/api/volatility")
def volatility(
    symbol: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    resolution: str = Query("auto"),
):
    if symbol not in ASSETS:
        raise HTTPException(400, f"unknown symbol {symbol}")
    res = _resolve_resolution(resolution, start, end)
    try:
        df = store.ohlcv(symbol, start, end, res)
    except store.DataUnavailable as exc:
        raise HTTPException(503, str(exc))
    close = df.set_index("ts")["close"]
    try:
        report = stats.volatility_report(close, res)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    report["symbol"] = symbol
    return report


@app.get("/api/correlation")
def correlation(
    start: datetime = Query(...),
    end: datetime = Query(...),
    resolution: str = Query("auto"),
):
    _guard_data()
    res = _resolve_resolution(resolution, start, end)
    wide = store.closes(SYMBOLS, start, end, res)
    if wide.empty:
        raise HTTPException(422, "no data in the selected window")
    result = stats.correlation_matrix(wide)
    result["resolution"] = res
    return result


@app.get("/api/correlation/pair")
def correlation_pair(
    a: str = Query(...),
    b: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    resolution: str = Query("auto"),
    window: int = Query(30, ge=3, le=500),
):
    for s in (a, b):
        if s not in ASSETS:
            raise HTTPException(400, f"unknown symbol {s}")
    res = _resolve_resolution(resolution, start, end)
    wide = store.closes([a, b], start, end, res)
    if wide.empty or a not in wide or b not in wide:
        raise HTTPException(422, "no overlapping data for this pair in the window")
    result = stats.rolling_correlation(wide[a], wide[b], window)
    result.update({"a": a, "b": b, "resolution": res})
    return result


@app.get("/api/patterns")
def patterns(
    symbol: str = Query(...),
    direction: str = Query("drop", pattern="^(drop|spike)$"),
    threshold: float = Query(0.05, gt=0, le=0.9, description="fractional move, e.g. 0.05 = 5%"),
    lookback: int = Query(1, ge=1, le=500),
    horizon: int = Query(24, ge=1, le=500),
    resolution: str = Query("1h"),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
):
    if symbol not in ASSETS:
        raise HTTPException(400, f"unknown symbol {symbol}")
    if resolution not in RESOLUTIONS:
        raise HTTPException(400, f"resolution must be one of {list(RESOLUTIONS)}")

    rng = store.full_range(symbol)
    if rng is None:
        raise HTTPException(503, "no data for this symbol — run the ingestion first")
    lo, hi = rng
    start = start or lo
    end = end or hi
    df = store.ohlcv(symbol, start, end, resolution)
    if df.empty:
        raise HTTPException(422, "no data in the selected window")
    close = df.set_index("ts")["close"]
    try:
        result = stats.pattern_scan(close, direction, threshold, lookback, horizon)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    result.update({
        "symbol": symbol, "direction": direction, "threshold": threshold,
        "lookback": lookback, "resolution": resolution,
    })
    return result


@app.get("/api/depth")
def depth(
    symbol: str = Query(...),
    at: datetime | None = Query(None, description="timestamp; defaults to latest bar"),
):
    if symbol not in ASSETS:
        raise HTTPException(400, f"unknown symbol {symbol}")
    rng = store.full_range(symbol)
    if rng is None:
        raise HTTPException(503, "no data for this symbol — run the ingestion first")
    lo, hi = rng
    at = at or hi
    at = min(max(at, lo), hi)
    # Use a short trailing window around `at` to get price + recent volume.
    df = store.ohlcv(symbol, at - timedelta(hours=1), at, "1m")
    if df.empty:
        df = store.ohlcv(symbol, lo, hi, "1d").tail(1)
    price = float(df["close"].iloc[-1])
    recent_volume = float(df["volume"].tail(60).sum())
    book = reconstruct_depth(price, recent_volume, seed=int(at.timestamp()))
    book.update({"symbol": symbol, "at": str(at)})
    return book
