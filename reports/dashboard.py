"""
HTML performance dashboard — all charts built with Plotly, embedded in a single
self-contained HTML file (no CDN required except Plotly CDN for rendering).
"""

from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

from crypto_crush.config import INITIAL_CAPITAL


# ── Colour palette ────────────────────────────────────────────────────────────
COLOURS = {
    "strategy_a": "#6C63FF",
    "strategy_b": "#FF6584",
    "hodl_eth":   "#F4A261",
    "aave_lend":  "#2EC4B6",
    "yearn":      "#8AC926",
}

LABELS = {
    "strategy_a": "LP Optimizer (A)",
    "strategy_b": "Yield Arb (B)",
    "hodl_eth":   "HODL ETH",
    "aave_lend":  "Aave Stable",
    "yearn":      "Yearn USDC",
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _align(series_dict: dict) -> dict:
    """Reindex all series to a common date range."""
    idx = None
    for s in series_dict.values():
        if idx is None:
            idx = s.index
        else:
            idx = idx.union(s.index)
    return {k: v.reindex(idx).ffill() for k, v in series_dict.items()}


# ── Individual chart builders ─────────────────────────────────────────────────

def _equity_chart(results: dict) -> go.Figure:
    fig = go.Figure()
    keys = ["strategy_a", "strategy_b", "hodl_eth", "aave_lend", "yearn"]
    for k in keys:
        eq = results[k]["equity"]
        fig.add_trace(go.Scatter(
            x=eq.index, y=eq.values,
            name=LABELS[k], line=dict(color=COLOURS[k], width=2),
            hovertemplate="%{y:$,.0f}<extra>" + LABELS[k] + "</extra>",
        ))
    fig.update_layout(
        title="Equity Curves (Starting Capital $100,000)",
        yaxis_title="Portfolio Value (USD)",
        xaxis_title="Date",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=480,
    )
    return fig


def _rolling_sharpe_chart(results: dict) -> go.Figure:
    fig = go.Figure()
    keys = ["strategy_a", "strategy_b", "hodl_eth", "aave_lend", "yearn"]
    for k in keys:
        rs = results[k]["rolling_sharpe"].dropna()
        fig.add_trace(go.Scatter(
            x=rs.index, y=rs.values,
            name=LABELS[k], line=dict(color=COLOURS[k], width=1.5),
            hovertemplate="%{y:.2f}<extra>" + LABELS[k] + "</extra>",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        title="Rolling 30-Day Sharpe Ratio",
        yaxis_title="Sharpe Ratio",
        xaxis_title="Date",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=380,
    )
    return fig


def _hex_to_rgba(hex_color: str, alpha: float = 0.15) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _drawdown_chart(results: dict) -> go.Figure:
    fig = go.Figure()
    keys = ["strategy_a", "strategy_b", "hodl_eth"]
    for k in keys:
        dd = results[k]["drawdown"].dropna() * 100
        fig.add_trace(go.Scatter(
            x=dd.index, y=dd.values,
            name=LABELS[k], fill="tozeroy",
            line=dict(color=COLOURS[k], width=1),
            fillcolor=_hex_to_rgba(COLOURS[k], 0.15),
            hovertemplate="%{y:.2f}%<extra>" + LABELS[k] + "</extra>",
        ))
    fig.update_layout(
        title="Drawdown (%)",
        yaxis_title="Drawdown (%)",
        xaxis_title="Date",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=350,
    )
    return fig


def _il_fee_chart(results: dict) -> go.Figure:
    """Cumulative fee revenue vs IL cost for Strategy A."""
    fee = results["strategy_a"].get("fee_returns", pd.Series(dtype=float))
    il  = results["strategy_a"].get("il_returns",  pd.Series(dtype=float))
    if fee.empty:
        return go.Figure(layout=go.Layout(title="IL vs Fee — no data"))

    cum_fee = (fee * INITIAL_CAPITAL).cumsum()
    cum_il  = (il.clip(upper=0) * INITIAL_CAPITAL).cumsum()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cum_fee.index, y=cum_fee.values,
        name="Cumulative Fee Revenue ($)", line=dict(color="#2EC4B6", width=2),
        hovertemplate="$%{y:,.0f}<extra>Fee Revenue</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=cum_il.index, y=cum_il.values,
        name="Cumulative IL Cost ($)", line=dict(color="#E63946", width=2),
        fill="tozeroy", fillcolor="rgba(230,57,70,0.1)",
        hovertemplate="$%{y:,.0f}<extra>IL Cost</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=cum_fee.index, y=(cum_fee + cum_il).values,
        name="Net P&L ($)", line=dict(color="#6C63FF", width=2, dash="dot"),
        hovertemplate="$%{y:,.0f}<extra>Net P&L</extra>",
    ))
    fig.update_layout(
        title="Strategy A — Fee Revenue vs Impermanent Loss",
        yaxis_title="Cumulative USD",
        xaxis_title="Date",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=380,
    )
    return fig


def _yield_diff_chart(results: dict) -> go.Figure:
    """Aave vs Compound APY differential timeseries for Strategy B."""
    arb_sig = results.get("arb_signals")
    if arb_sig is None or arb_sig.empty:
        return go.Figure(layout=go.Layout(title="Yield Differential — no data"))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=arb_sig.index, y=arb_sig["aave_apy"],
        name="Aave V3 USDC APY (%)", line=dict(color="#2EC4B6", width=2),
        hovertemplate="%{y:.2f}%<extra>Aave</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=arb_sig.index, y=arb_sig["comp_apy"],
        name="Compound USDC APY (%)", line=dict(color="#F4A261", width=2),
        hovertemplate="%{y:.2f}%<extra>Compound</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=arb_sig.index, y=arb_sig["differential"].abs(),
        name="|Differential| (%)", line=dict(color="#FF6584", width=1.5, dash="dot"),
        hovertemplate="%{y:.3f}%<extra>|Diff|</extra>",
    ))

    # Mark rotation events
    rotations = arb_sig[arb_sig["signal"] == "ROTATE"]
    if not rotations.empty:
        fig.add_trace(go.Scatter(
            x=rotations.index,
            y=rotations["aave_apy"].values,
            mode="markers",
            marker=dict(symbol="triangle-up", size=10, color="#E63946"),
            name="Rotation Event",
            hovertemplate="Rotate to %{text}<extra></extra>",
            text=rotations["protocol"].values,
        ))

    fig.update_layout(
        title="Strategy B — Lending Rate Differential (Aave vs Compound)",
        yaxis_title="APY (%)",
        xaxis_title="Date",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=380,
    )
    return fig


def _risk_table(results: dict) -> go.Figure:
    """Risk comparison table."""
    keys   = ["strategy_a", "strategy_b", "hodl_eth", "aave_lend", "yearn"]
    labels = [LABELS[k] for k in keys]
    m_list = [results[k]["metrics"] for k in keys]

    def pct(v): return f"{v*100:.2f}%" if not np.isnan(v) else "N/A"
    def f2(v):  return f"{v:.2f}"     if not np.isnan(v) else "N/A"

    fig = go.Figure(go.Table(
        header=dict(
            values=["Strategy", "Ann Return", "Ann Vol", "Sharpe", "Sortino",
                    "Max Drawdown", "Calmar"],
            fill_color="#6C63FF",
            font=dict(color="white", size=12),
            align="center",
        ),
        cells=dict(
            values=[
                labels,
                [pct(m["ann_return"])   for m in m_list],
                [pct(m["ann_vol"])      for m in m_list],
                [f2(m["sharpe"])        for m in m_list],
                [f2(m["sortino"])       for m in m_list],
                [pct(m["max_drawdown"]) for m in m_list],
                [f2(m["calmar"])        for m in m_list],
            ],
            fill_color=[["#f0f0ff" if i % 2 == 0 else "white" for i in range(len(keys))]]*7,
            align="center",
            font=dict(size=11),
        ),
    ))
    fig.update_layout(title="Risk & Return Comparison Table", height=280)
    return fig


# ── HTML assembly ─────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Crypto Crush — DeFi Yield Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f0f1a; color: #e0e0f0; }}
    header {{ background: linear-gradient(135deg,#6C63FF,#FF6584); padding: 2rem; text-align: center; }}
    header h1 {{ font-size: 2rem; font-weight: 700; }}
    header p  {{ opacity: 0.85; margin-top: .4rem; }}
    .kpi-bar {{ display: flex; gap: 1rem; flex-wrap: wrap; padding: 1.5rem 2rem;
                background: #16162a; border-bottom: 1px solid #2a2a4a; }}
    .kpi {{ flex: 1; min-width: 140px; background: #1e1e36; border-radius: 8px;
             padding: 1rem; text-align: center; }}
    .kpi .val {{ font-size: 1.6rem; font-weight: 700; color: #6C63FF; }}
    .kpi .lbl {{ font-size: .75rem; color: #9090b0; margin-top: .3rem; }}
    .section {{ padding: 1.5rem 2rem; }}
    .section h2 {{ font-size: 1.1rem; color: #9090c0; margin-bottom: 1rem;
                   text-transform: uppercase; letter-spacing: .08em; }}
    .chart-grid {{ display: grid; gap: 1.5rem; }}
    .chart-grid.two {{ grid-template-columns: repeat(auto-fit, minmax(480px,1fr)); }}
    .chart-box {{ background: #1a1a2e; border-radius: 12px; padding: 1rem;
                  border: 1px solid #2a2a4a; }}
    footer {{ text-align: center; padding: 1.5rem; color: #555575; font-size: .8rem; }}
  </style>
</head>
<body>
<header>
  <h1>&#128200; Crypto Crush — DeFi Yield Strategy Dashboard</h1>
  <p>Quantitative analysis of Uniswap V3 LP optimisation &amp; cross-protocol yield arbitrage &bull; {date}</p>
</header>

<div class="kpi-bar">
{kpis}
</div>

<div class="section">
  <h2>Equity Curves</h2>
  <div class="chart-box" id="equity"></div>
</div>

<div class="section">
  <h2>Rolling Sharpe &amp; Drawdown</h2>
  <div class="chart-grid two">
    <div class="chart-box" id="sharpe"></div>
    <div class="chart-box" id="drawdown"></div>
  </div>
</div>

<div class="section">
  <h2>Strategy Breakdown</h2>
  <div class="chart-grid two">
    <div class="chart-box" id="il_fee"></div>
    <div class="chart-box" id="yield_diff"></div>
  </div>
</div>

<div class="section">
  <h2>Risk Comparison</h2>
  <div class="chart-box" id="risk_table"></div>
</div>

<footer>
  Generated by Crypto Crush on {date} &bull; Data: DefiLlama, Etherscan &bull; Not financial advice.
</footer>

<script>
var PLOTLY_CONFIG = {{displayModeBar: true, responsive: true}};
{chart_scripts}
</script>
</body>
</html>
"""


def _kpi_html(results: dict) -> str:
    kpis = []
    for key, label in LABELS.items():
        m = results[key]["metrics"]
        ann = m["ann_return"]
        colour = "#2EC4B6" if ann >= 0 else "#E63946"
        kpis.append(
            f'<div class="kpi"><div class="val" style="color:{colour}">'
            f'{ann*100:+.1f}%</div><div class="lbl">{label}<br>Ann. Return</div></div>'
        )
    return "\n".join(kpis)


def _fig_script(div_id: str, fig: go.Figure) -> str:
    json_str = pio.to_json(fig)
    return (
        f"var fig_{div_id} = {json_str};\n"
        f"Plotly.newPlot('{div_id}', fig_{div_id}.data, fig_{div_id}.layout, PLOTLY_CONFIG);\n"
    )


def generate_html_report(results: dict, output_path: str = "report.html") -> str:
    """Build and write the full HTML dashboard; return the path."""
    print("\n[Dashboard] Building Plotly charts …")

    figs = {
        "equity":     _equity_chart(results),
        "sharpe":     _rolling_sharpe_chart(results),
        "drawdown":   _drawdown_chart(results),
        "il_fee":     _il_fee_chart(results),
        "yield_diff": _yield_diff_chart(results),
        "risk_table": _risk_table(results),
    }

    scripts = "\n".join(_fig_script(div_id, fig) for div_id, fig in figs.items())

    html = _HTML_TEMPLATE.format(
        date=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        kpis=_kpi_html(results),
        chart_scripts=scripts,
    )

    out = Path(output_path)
    out.write_text(html, encoding="utf-8")
    print(f"[Dashboard] Report saved → {out.resolve()}")
    return str(out.resolve())
