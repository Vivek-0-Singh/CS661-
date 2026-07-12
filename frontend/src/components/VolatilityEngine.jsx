import { useState } from "react";
import { Plot } from "../plot.jsx";
import { Panel, Status, Stat } from "./ui.jsx";
import { useApp } from "../state.jsx";
import { api } from "../api";
import { useFetch } from "../hooks";
import { COLORS, baseLayout, plotConfig } from "../theme";

const SCENARIOS = ["normal", "stress", "crash"];
// Traffic-light metaphor, but darkened for AA contrast on white and
// separated in luminance so the three states survive colour-blind viewing.
const SCEN_COLOR = { normal: "#1a7f37", stress: "#9a6700", crash: "#cf222e" };
const pct = (x) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

const SCEN_GLOW = { normal: "ok", stress: "warn", crash: "crit" };

/** View 4 — Volatility Engine: risk analytics with normal/stress/crash tail risk. */
export default function VolatilityEngine({ index = 0 }) {
  const { asset, window } = useApp();
  const [scenario, setScenario] = useState("normal");
  const [tab, setTab] = useState("risk");

  const { data, loading, error } = useFetch(
    () => api.volatility({ symbol: asset, start: window.start, end: window.end, resolution: "auto" }),
    [asset, window.start, window.end]
  );

  const sc = data?.scenarios?.[scenario];
  const thresholds = ["0.05", "0.10", "0.15", "0.20"];

  const rollFig = {
    data: [
      {
        type: "scatter",
        mode: "lines",
        x: (data?.rolling ?? []).map((r) => r.ts),
        y: (data?.rolling ?? []).map((r) => r.vol),
        line: { color: COLORS.accent, width: 1.5 },
        hovertemplate: "%{x|%b %d}  %{y:.1%}<extra></extra>",
      },
    ],
    layout: baseLayout({
      height: 104,
      margin: { l: 46, r: 10, t: 4, b: 28 },
      xaxis: { type: "date", gridcolor: COLORS.grid },
      yaxis: { tickformat: ".0%", gridcolor: COLORS.grid },
    }),
  };

  const probFig = {
    data: [
      {
        type: "bar",
        x: thresholds.map((t) => `${Math.round(+t * 100)}%`),
        y: thresholds.map((t) => sc?.drop_probs?.[t] ?? 0),
        marker: { color: SCEN_COLOR[scenario] },
        hovertemplate: "≥%{x} drop:  %{y:.2%}<extra></extra>",
      },
    ],
    layout: baseLayout({
      height: 112,
      margin: { l: 46, r: 10, t: 4, b: 30 },
      xaxis: {
        title: { text: `drop within one ${data?.resolution ?? ""} bar`, font: { size: 10 } },
        gridcolor: COLORS.grid,
      },
      yaxis: { tickformat: ".1%", gridcolor: COLORS.grid },
    }),
  };

  // Return distribution: observed histogram vs the normal fit at the same
  // mean/std — the visible gap in the tails is what kurtosis measures.
  const hist = data?.histogram;
  const centers = hist
    ? hist.bins.slice(0, -1).map((b, i) => ((b + hist.bins[i + 1]) / 2) * 100)
    : [];
  const binW = hist && hist.bins.length > 1 ? hist.bins[1] - hist.bins[0] : 0;
  const mu = data?.distribution?.mean ?? 0;
  const sd = data?.distribution?.std ?? 1;
  const nObs = data?.distribution?.n ?? 0;
  const normY = centers.map((cPct) => {
    const x = cPct / 100;
    const pdf = Math.exp(-((x - mu) ** 2) / (2 * sd * sd)) / (sd * Math.sqrt(2 * Math.PI));
    return pdf * nObs * binW;
  });
  const distFig = {
    data: [
      {
        type: "bar",
        x: centers,
        y: hist?.counts ?? [],
        marker: { color: "rgba(9,105,218,0.55)" },
        name: "observed",
        hovertemplate: "%{x:.2f}%: %{y} bars<extra>observed</extra>",
      },
      {
        type: "scatter",
        mode: "lines",
        x: centers,
        y: normY,
        line: { color: COLORS.warn, width: 1.5 },
        name: "normal fit",
        hovertemplate: "%{x:.2f}%: %{y:.1f}<extra>normal fit</extra>",
      },
    ],
    layout: baseLayout({
      height: 232,
      margin: { l: 46, r: 10, t: 6, b: 30 },
      bargap: 0,
      showlegend: true,
      legend: {
        orientation: "h", x: 1, xanchor: "right", y: 1.1, yanchor: "bottom",
        font: { size: 10, color: COLORS.muted }, bgcolor: "rgba(0,0,0,0)",
      },
      xaxis: {
        title: { text: `single ${data?.resolution ?? ""} bar log return`, font: { size: 10 } },
        ticksuffix: "%",
        gridcolor: COLORS.grid,
      },
      yaxis: { title: { text: "count", font: { size: 10 } }, gridcolor: COLORS.grid },
    }),
  };

  return (
    <Panel
      index={index}
      glow={data ? SCEN_GLOW[scenario] : undefined}
      className="span-3"
      title="Volatility Engine"
      subtitle={data ? `ann. vol ${pct(data.annualized_vol)}` : "risk analytics"}
      actions={
        <>
          <div className="seg">
            <button className={tab === "risk" ? "active" : ""} onClick={() => setTab("risk")}>
              risk
            </button>
            <button className={tab === "dist" ? "active" : ""} onClick={() => setTab("dist")}>
              dist
            </button>
          </div>
          <div className="seg">
            {SCENARIOS.map((s) => (
              <button key={s} className={scenario === s ? "active" : ""} onClick={() => setScenario(s)}>
                {s}
              </button>
            ))}
          </div>
        </>
      }
    >
      <Status loading={loading} error={error} empty={data && !data.scenarios}>
        {data && (
          <>
            {tab === "risk" ? (
              <>
                <div style={{ color: COLORS.muted, fontSize: 11, margin: "2px 0 2px" }}>
                  Rolling annualized volatility
                </div>
                <Plot data={rollFig.data} layout={rollFig.layout} config={plotConfig} style={{ width: "100%" }} useResizeHandler />
                <div style={{ color: COLORS.muted, fontSize: 11, margin: "6px 0 2px" }}>
                  P(drop ≥ threshold) — <b style={{ color: SCEN_COLOR[scenario] }}>{scenario}</b> scenario
                </div>
                <Plot data={probFig.data} layout={probFig.layout} config={plotConfig} style={{ width: "100%" }} useResizeHandler />
              </>
            ) : (
              <>
                <div style={{ color: COLORS.muted, fontSize: 11, margin: "2px 0 2px" }}>
                  Return distribution — observed vs normal fit (fatter tails ⇒ more extreme moves)
                </div>
                <Plot data={distFig.data} layout={distFig.layout} config={plotConfig} style={{ width: "100%" }} useResizeHandler />
              </>
            )}
            <div className="stats-row">
              <Stat label="VaR 95%" num={sc?.var95} format={(v) => `${(v * 100).toFixed(1)}%`} tone="down" />
              <Stat label="VaR 99%" num={sc?.var99} format={(v) => `${(v * 100).toFixed(1)}%`} tone="down" />
              <Stat label="CVaR 95%" num={sc?.cvar95} format={(v) => `${(v * 100).toFixed(1)}%`} tone="down" />
              <Stat label="Kurtosis" num={data.distribution.kurtosis} format={(v) => v.toFixed(2)} />
            </div>
          </>
        )}
      </Status>
    </Panel>
  );
}
