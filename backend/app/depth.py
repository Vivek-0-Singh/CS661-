"""Historical order-book depth reconstruction.

Live depth comes from Binance's WebSocket (handled by the ws-server). For past
timestamps there is no real book, so we synthesise a plausible depth profile
around the close price, scaled by recent traded volume, with a couple of
'walls'. This is an approximation for structural analysis, not real quotes.
"""
from __future__ import annotations

import numpy as np


def reconstruct_depth(price: float, recent_volume: float, levels: int = 20, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed & 0xFFFFFFFF)
    tick = max(price * 0.0005, 1e-9)              # ~5 bps spacing
    base = max(recent_volume, 1.0) / levels

    wall_bid = rng.integers(1, levels + 1)
    wall_ask = rng.integers(1, levels + 1)

    bids, asks = [], []
    cum_b = cum_a = 0.0
    for i in range(1, levels + 1):
        decay = np.exp(-i / levels)
        size_b = base * decay * (0.5 + rng.random())
        size_a = base * decay * (0.5 + rng.random())
        if i == wall_bid:
            size_b *= 6.0
        if i == wall_ask:
            size_a *= 6.0
        cum_b += size_b
        cum_a += size_a
        bids.append({"price": price - i * tick, "size": size_b, "cum": cum_b})
        asks.append({"price": price + i * tick, "size": size_a, "cum": cum_a})

    return {
        "mid": price,
        "bids": bids,   # descending away from mid
        "asks": asks,
        "synthetic": True,
    }
