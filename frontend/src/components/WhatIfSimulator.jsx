import { useState } from "react";
import { Plot } from "../plot.jsx";
import { Panel, Status, Stat } from "./ui.jsx";
import { useApp } from "../state.jsx";
import { api } from "../api";
import { useFetch } from "../hooks";
import { COLORS, baseLayout, plotConfig } from "../theme";

const pct = (x) => (x == null ? "—" : `${(x * 100).toFixed(2)}%`);

/**
 * View 3 — The What-If Simulator: pattern hypothesis tester. Scans all history
 * for a trigger (e.g. a sharp hourly drop) and shows the distribution of
 * forward price paths after each occurrence.
 */
export default function WhatIfSimulator() {
  const { asset } = useApp();
  const [form, setForm] = useState({
    direction: "drop",
    thresholdPct: 2,
    lookback: 1,
    horizon: 24,
    resolution: "1h",
  });
  const [submitted, setSubmitted] = useState(form);

  const { data, loading, error } = useFetch(
    () =>
      api.patterns({
        symbol: asset,
        direction: submitted.direction,
        threshold: submitted.thresholdPct / 100,
        lookback: submitted.lookback,
        horizon: submitted.horizon,
        resolution: submitted.resolution,
      }),
    [asset, submitted]
  );

  const upd = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.type === "number" ? +e.target.value : e.target.value }));

  const bands = data?.bands ?? [];
  const steps = bands.map((b) => b.step);
  const asPct = (key) => bands.map((b) => b[key] * 100);

  const fanFig = {
    data: [
      { x: steps, y: asPct("p10"), mode: "lines", line: { width: 0 }, hoverinfo: "skip" },
      {
        x: steps, y: asPct("p90"), mode: "lines", line: { width: 0 },
        fill: "tonexty", fillcolor: "rgba(88,166,255,0.10)", hoverinfo: "skip",
      },
      { x: steps, y: asPct("p25"), mode: "lines", line: { width: 0 }, hoverinfo: "skip" },
      {
        x: steps, y: asPct("p75"), mode: "lines", line: { width: 0 },
        fill: "tonexty", fillcolor: "rgba(88,166,255,0.22)", hoverinfo: "skip",
      },
      {
        x: steps, y: asPct("p50"), mode: "lines", line: { color: COLORS.accent, width: 2 },
        name: "median", hovertemplate: "step %{x}: %{y:.2f}%<extra>median</extra>",
      },
      {
        x: steps, y: asPct("mean"), mode: "lines", line: { color: "#f0b429", width: 1.5, dash: "dot" },
        name: "mean", hovertemplate: "step %{x}: %{y:.2f}%<extra>mean</extra>",
      },
    ],
    layout: baseLayout({
      height: 240,
      margin: { l: 50, r: 14, t: 10, b: 34 },
      xaxis: { title: { text: `periods after trigger (${submitted.resolution})`, font: { size: 10 } }, gridcolor: COLORS.grid },
      yaxis: { title: { text: "forward return", font: { size: 10 } }, ticksuffix: "%", gridcolor: COLORS.grid, zeroline: true, zerolinecolor: COLORS.border },
    }),
  };

  const t = data?.terminal;

  return (
    <Panel
      className="span-6"
      title="The What-If Simulator"
      subtitle="pattern hypothesis tester · scans all history"
    >
      <div className="controls">
        <div className="field">
          <label>trigger</label>
          <select value={form.direction} onChange={upd("direction")}>
            <option value="drop">price drops</option>
            <option value="spike">price spikes</option>
          </select>
        </div>
        <div className="field">
          <label>move ≥ (%)</label>
          <input type="number" min="0.5" step="0.5" value={form.thresholdPct} onChange={upd("thresholdPct")} />
        </div>
        <div className="field">
          <label>over (periods)</label>
          <input type="number" min="1" value={form.lookback} onChange={upd("lookback")} />
        </div>
        <div className="field">
          <label>track ahead</label>
          <input type="number" min="1" value={form.horizon} onChange={upd("horizon")} />
        </div>
        <div className="field">
          <label>resolution</label>
          <select value={form.resolution} onChange={upd("resolution")}>
            <option value="1h">1h</option>
            <option value="1d">1d</option>
            <option value="1m">1m</option>
          </select>
        </div>
        <button className="btn" onClick={() => setSubmitted({ ...form })}>
          Run scan
        </button>
        <div className="stats-row" style={{ marginLeft: "auto" }}>
          <Stat label="events found" value={data?.n_events ?? "…"} />
          <Stat label="win rate" value={t ? pct(t.win_rate) : "…"} tone={t && t.win_rate >= 0.5 ? "up" : "down"} />
          <Stat label="mean outcome" value={t ? pct(t.mean) : "…"} tone={t && t.mean >= 0 ? "up" : "down"} />
          <Stat label="best / worst" value={t ? `${pct(t.best)} / ${pct(t.worst)}` : "…"} />
        </div>
      </div>
      <Status loading={loading} error={error}>
        {data && data.n_events > 0 ? (
          <>
            <div style={{ color: COLORS.muted, fontSize: 11, marginBottom: 2 }}>
              Forward return distribution after a {submitted.thresholdPct}%{" "}
              {submitted.direction} over {submitted.lookback} {submitted.resolution} — {data.n_events}{" "}
              historical occurrences (band = 10–90th &amp; 25–75th pctile)
            </div>
            <Plot data={fanFig.data} layout={fanFig.layout} config={plotConfig} style={{ width: "100%" }} useResizeHandler />
          </>
        ) : data ? (
          <div className="status">
            No historical occurrences of this pattern in the available data — loosen the trigger.
          </div>
        ) : null}
      </Status>
    </Panel>
  );
}
