import { useState } from "react";
import { Plot } from "../plot.jsx";
import { Panel, Status, Stat } from "./ui.jsx";
import { useApp } from "../state.jsx";
import { api } from "../api";
import { useFetch } from "../hooks";
import { COLORS, baseLayout, plotConfig } from "../theme";

const SCENARIOS = ["normal", "stress", "crash"];
const SCEN_COLOR = { normal: "#3fb950", stress: "#f0b429", crash: "#f85149" };
const pct = (x) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

/** View 4 — Volatility Engine: risk analytics with normal/stress/crash tail risk. */
export default function VolatilityEngine() {
  const { asset, window } = useApp();
  const [scenario, setScenario] = useState("normal");

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
      height: 120,
      margin: { l: 46, r: 10, t: 6, b: 24 },
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
      height: 130,
      margin: { l: 46, r: 10, t: 6, b: 24 },
      xaxis: { title: { text: "single-period drop", font: { size: 10 } }, gridcolor: COLORS.grid },
      yaxis: { tickformat: ".1%", gridcolor: COLORS.grid },
    }),
  };

  return (
    <Panel
      className="span-2"
      title="Volatility Engine"
      subtitle={data ? `ann. vol ${pct(data.annualized_vol)}` : "risk analytics"}
      actions={
        <div className="seg">
          {SCENARIOS.map((s) => (
            <button key={s} className={scenario === s ? "active" : ""} onClick={() => setScenario(s)}>
              {s}
            </button>
          ))}
        </div>
      }
    >
      <Status loading={loading} error={error} empty={data && !data.scenarios}>
        {data && (
          <>
            <div style={{ color: COLORS.muted, fontSize: 11, margin: "2px 0 2px" }}>
              Rolling annualized volatility
            </div>
            <Plot data={rollFig.data} layout={rollFig.layout} config={plotConfig} style={{ width: "100%" }} useResizeHandler />
            <div style={{ color: COLORS.muted, fontSize: 11, margin: "6px 0 2px" }}>
              P(drop ≥ threshold) — <b style={{ color: SCEN_COLOR[scenario] }}>{scenario}</b> scenario
            </div>
            <Plot data={probFig.data} layout={probFig.layout} config={plotConfig} style={{ width: "100%" }} useResizeHandler />
            <div className="stats-row">
              <Stat label="VaR 95%" value={pct(sc?.var95)} tone="down" />
              <Stat label="VaR 99%" value={pct(sc?.var99)} tone="down" />
              <Stat label="CVaR 95%" value={pct(sc?.cvar95)} tone="down" />
              <Stat label="Kurtosis" value={data.distribution.kurtosis.toFixed(2)} />
            </div>
          </>
        )}
      </Status>
    </Panel>
  );
}
