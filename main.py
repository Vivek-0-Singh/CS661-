"""
Crypto Crush — DeFi Yield Strategy CLI

Usage (from inside crypto_crush/ folder):
    python main.py --strategy all --period 180d --output report.html
    python main.py --strategy a --period 90d --output strat_a.html
    python main.py --strategy b --output strat_b.html

Usage (from repo root):
    python crypto_crush/main.py --strategy all
"""

import argparse
import sys
import io
import time
from pathlib import Path

# Force UTF-8 on Windows console so Unicode in print() doesn't crash
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# main.py lives inside crypto_crush/, so go up one level to find the package
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))


def parse_args():
    p = argparse.ArgumentParser(
        description="Crypto Crush -- DeFi Yield Engineering Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--strategy", choices=["all", "a", "b"], default="all",
        help="Which strategy to run (default: all)",
    )
    p.add_argument(
        "--period", default="180d",
        help="Lookback period e.g. 90d, 180d (default: 180d)",
    )
    p.add_argument(
        "--output", default=str(_HERE / "report.html"),
        help="Output HTML report path (default: crypto_crush/report.html)",
    )
    p.add_argument(
        "--no-cache", action="store_true",
        help="Bust cache and re-fetch all data",
    )
    return p.parse_args()


def parse_days(period: str) -> int:
    period = period.strip().lower()
    if period.endswith("d"):
        return int(period[:-1])
    if period.endswith("m"):
        return int(period[:-1]) * 30
    return int(period)


def main():
    args   = parse_args()
    days   = parse_days(args.period)
    t0     = time.time()

    print("=" * 60)
    print("  Crypto Crush -- DeFi Yield Engineering Framework")
    print("=" * 60)
    print(f"  Strategy : {args.strategy.upper()}")
    print(f"  Period   : {days} days")
    print(f"  Output   : {args.output}")
    print()

    # ── Override HISTORY_DAYS from CLI ────────────────────────────────────────
    import crypto_crush.config as cfg
    cfg.HISTORY_DAYS = days

    # ── Imports (after config patch) ──────────────────────────────────────────
    from crypto_crush.data import defillama, etherscan
    from crypto_crush.strategies import lp_optimizer, yield_arb
    from crypto_crush.backtest import engine
    from crypto_crush.reports.dashboard import generate_html_report

    if args.no_cache:
        import shutil
        shutil.rmtree(cfg.CACHE_DIR, ignore_errors=True)
        cfg.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print("  Cache cleared.\n")

    # ── Step 1: Fetch data ────────────────────────────────────────────────────
    print("-" * 60)
    print("STEP 1 -- Fetching live data from DefiLlama + Etherscan")
    print("-" * 60)

    all_pools = defillama.get_all_pools()
    print(f"  Loaded {len(all_pools):,} yield pools from DefiLlama")

    eth_price_df         = defillama.get_eth_price_history(days)
    uni_df, _            = defillama.get_uniswap_eth_usdc(all_pools)
    aave_df, _           = defillama.get_aave_usdc(all_pools)
    comp_df, _           = defillama.get_compound_usdc(all_pools)
    yearn_df, _          = defillama.get_yearn_usdc(all_pools)

    gas_usd = etherscan.gas_cost_usd(cfg.GAS_UNITS_ROTATION)
    print(f"  Rotation gas cost: ${gas_usd:.2f}")

    # ── Step 2: Run strategies ────────────────────────────────────────────────
    print()
    print("-" * 60)
    print("STEP 2 -- Running strategies")
    print("-" * 60)

    lp_result  = None
    arb_result = None

    if args.strategy in ("all", "a"):
        lp_result = lp_optimizer.run(uni_df, eth_price_df)

    if args.strategy in ("all", "b"):
        arb_result = yield_arb.run(aave_df, comp_df, gas_usd)

    # ── Step 3: Backtest ──────────────────────────────────────────────────────
    print()
    print("-" * 60)
    print("STEP 3 -- Backtesting & benchmarking")
    print("-" * 60)

    if lp_result is None:
        import pandas as pd, numpy as np
        dummy_idx  = eth_price_df.index
        dummy_feat = eth_price_df.copy()
        dummy_feat["apy"] = aave_df["apy"].reindex(dummy_idx).fillna(4.0)
        dummy_feat["vol_30d"] = 0.4
        dummy_feat["vol_5d"]  = 0.4
        dummy_sig = pd.DataFrame(
            {"signal": "HOLD", "P_a": np.nan, "P_b": np.nan,
             "opt_r": np.nan, "net_apy_est": np.nan},
            index=dummy_idx,
        )
        lp_result = {"features": dummy_feat, "signals": dummy_sig, "name": "LP (disabled)"}

    if arb_result is None:
        import pandas as pd
        dummy_sig = pd.DataFrame(
            {"signal": "HOLD", "protocol": "aave",
             "current_apy": aave_df["apy"],
             "aave_apy": aave_df["apy"],
             "comp_apy": comp_df["apy"].reindex(aave_df.index).fillna(4.0),
             "differential": 0.0, "net_spread": 0.0},
            index=aave_df.index,
        )
        arb_result = {"features": aave_df, "signals": dummy_sig, "name": "Arb (disabled)"}

    results = engine.run_all(
        lp_result=lp_result,
        arb_result=arb_result,
        eth_df=eth_price_df,
        aave_df=aave_df,
        yearn_df=yearn_df,
        gas_usd=gas_usd,
    )

    # ── Step 4: Generate report ───────────────────────────────────────────────
    print()
    print("-" * 60)
    print("STEP 4 -- Generating HTML dashboard")
    print("-" * 60)

    report_path = generate_html_report(results, args.output)

    elapsed = time.time() - t0
    print()
    print("=" * 60)
    print(f"  Done in {elapsed:.1f}s")
    print(f"  Report  -> {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
