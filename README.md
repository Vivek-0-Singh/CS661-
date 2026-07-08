# Crypto Crush — Quantitative Framework for DeFi Yield

A complete quantitative research and backtesting system for DeFi yield strategies on Ethereum, built with real live data from **DefiLlama** and **Etherscan**.

---

## Quick Start

```bash
# from the repo root (d:\avellaneda-stoikov\)

# 1. Install dependencies
pip install -r requirements.txt

# 2. Run full analysis (180 days, both strategies, all benchmarks)
python main.py --strategy all --period 180d --output report.html

# 3. Strategy A only (LP Optimizer)
python main.py --strategy a --output lp_report.html

# 4. Strategy B only (Yield Arbitrage)
python main.py --strategy b --output arb_report.html

# 5. Force re-fetch (ignore cache)
python main.py --no-cache
```

Open `report.html` in any browser — fully self-contained, no server needed.

---

## Project Structure

```
crypto_crush/
├── config.py               # API keys, thresholds, constants
├── data/
│   ├── defillama.py        # DefiLlama API client + mock fallbacks
│   ├── etherscan.py        # Etherscan gas oracle
│   └── cache.py            # File-based JSON cache (6h TTL)
├── strategies/
│   ├── lp_optimizer.py     # Strategy A: Uniswap V3 LP range optimiser
│   └── yield_arb.py        # Strategy B: Aave vs Compound rate arbitrage
├── backtest/
│   ├── engine.py           # Vectorized backtesting (from scratch)
│   └── metrics.py          # Sharpe, Sortino, drawdown, Calmar, IL
└── reports/
    ├── dashboard.py        # Plotly HTML report generator
    └── research_report.md  # Protocol analysis (Ethereum, Uniswap V3, Aave V3)
main.py                     # CLI entry point (repo root)
requirements.txt
```

---

## Data Sources

| Source | Data | Auth |
|--------|------|------|
| DefiLlama Yields API | Pool APYs, TVL, historical | None |
| DefiLlama Coins API  | ETH price history (WETH)   | None |
| Etherscan API        | Gas oracle, live ETH price | Free key |

Responses are cached locally for 6 hours. If any API is unavailable, the system falls back to statistically realistic mock data automatically.

---

## Strategies

### Strategy A — Uniswap V3 LP Optimizer

1. Fetch ETH/USDC 0.05% pool APY + ETH price history
2. Compute rolling 30-day realized volatility as regime signal
3. Optimize tick range `[P_a, P_b]` via `scipy.optimize.minimize_scalar`:
   - Objective: maximize `E[fee × concentration] − E[IL_cost]`
4. ENTER when vol < 40th percentile; EXIT when 5-day vol spikes 1.8× 30-day vol
5. Rebalance range every 7 days

IL formula: `IL = 2√k / (1+k) − 1` where `k = P_new / P_entry`

### Strategy B — Cross-Protocol Yield Arbitrage

1. Fetch Aave V3 USDC and Compound V3 USDC APY history
2. Compute gas cost per rotation (Etherscan oracle × 350k gas × ETH price)
3. Rotate capital when `|APY_diff| > 0.40%` after netting gas drag
4. Enforce 5-day minimum hold between rotations

---

## Performance Metrics Computed

Annualised Return, Annualised Volatility, Sharpe (rf=5%), Sortino, Max Drawdown, Calmar Ratio

**Benchmarks:** HODL ETH · Aave Stable Lending · Yearn USDC Vault

---

## Configuration

Key parameters in `crypto_crush/config.py`:

```python
ETHERSCAN_API_KEY    = "your-key"
HISTORY_DAYS         = 180
LP_VOL_ENTRY_PCTILE  = 40     # enter LP when vol below this percentile
LP_VOL_EXIT_MULT     = 1.8    # exit when vol spikes this multiple
ARB_THRESHOLD_PCT    = 0.40   # min APY spread to trigger rotation
GAS_UNITS_ROTATION   = 350_000
```
