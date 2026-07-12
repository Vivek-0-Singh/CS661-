import { useEffect, useState } from "react";
import { Plot } from "../plot.jsx";
import { Panel, Status, Stat } from "./ui.jsx";
import { useApp } from "../state.jsx";
import { api } from "../api";
import { useFetch } from "../hooks";
import { COLORS, baseLayout, plotConfig } from "../theme";

const pct = (x) => (x == null ? "—" : `${(x * 100).toFixed(2)}%`);

/**
 * View 3 — The What-If Simulator: pattern hypothesis tester. Scans history
 * (all of it, or just the brushed window) for a trigger and shows the
 * distribution of forward price paths after each occurrence. Trigger
 * timestamps are shared with the Time Machine, which marks them on the
 * candlestick chart.
 */
export default function WhatIfSimulator({ index = 0 }) {
  const { asset, window, setEvents } = useApp();
  const [form, setForm] = useState({
    direction: "drop",
    thresholdPct: 2,
    lookback: 1,
    horizon: 24,
    resolution: "1h",
    scope: "all",
  });
  const [submitted, setSubmitted] = useState(form);

  const inWindow = submitted.scope === "window";
  const { data, loading, error } = useFetch(
    () =>
      api.patterns({
        symbol: asset,
        direction: submitted.direction,
        threshold: submitted.thresholdPct / 100,
        lookback: submitted.lookback,
        horizon: submitted.horizon,
        resolution: submitted.resolution,
        ...(inWindow ? { start: window.start, end: window.end } : {}),
      }),
    [asset, submitted, inWindow ? window.start : null, inWindow ? window.end : null]
  );

  // Share trigger timestamps so the Time Machine can mark them on the chart.
  useEffect(() => {
    setEvents(data?.sample_events ?? []);
  }, [data, setEvents]);

  const upd = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.type === "number" ? +e.target.value : e.target.value }));

  const bands = data?.bands ?? [];
  const steps = bands.map((b) => b.step);
  const asPct = (key) => bands.map((b) => b[key] * 100);

  const fanFig = {
    data: [
      { x: steps, y: asPct("p10"), mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false },
      {
        x: steps, y: asPct("p90"), mode: "lines", line: { width: 0 },
        fill: "tonexty", fillcolor: "rgba(9,105,218,0.09)", hoverinfo: "skip", showlegend: false,
      },
      { x: steps, y: asPct("p25"), mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false },
      {
        x: steps, y: asPct("p75"), mode: "lines", line: { width: 0 },
        fill: "tonexty", fillcolor: "rgba(9,105,218,0.18)", hoverinfo: "skip", showlegend: false,
      },
      {
        x: steps, y: asPct("p50"), mode: "lines", line: { color: COLORS.accent, width: 2 },
        name: "median", hovertemplate: "step %{x}: %{y:.2f}%<extra>median</extra>",
      },
      {
        x: steps, y: asPct("mean"), mode: "lines", line: { color: COLORS.warn, width: 1.5, dash: "dot" },
        name: "mean", hovertemplate: "step %{x}: %{y:.2f}%<extra>mean</extra>",
      },
    ],
    layout: baseLayout({
      height: 170,
      margin: { l: 46, r: 12, t: 6, b: 30 },
      showlegend: true,
      legend: {
        orientation: "h",
        x: 1,
        xanchor: "right",
        y: 1.12,
        yanchor: "bottom",
        font: { size: 10, color: COLORS.muted },
        bgcolor: "rgba(0,0,0,0)",
      },
      xaxis: { title: { text: `periods after trigger (${submitted.resolution})`, font: { size: 10 } }, gridcolor: COLORS.grid },
      yaxis: { title: { text: "forward return", font: { size: 10 } }, ticksuffix: "%", gridcolor: COLORS.grid, zeroline: true, zerolinecolor: COLORS.border },
    }),
  };

  const t = data?.terminal;

  return (
    <Panel
      index={index}
      className="span-3"
      title="The What-If Simulator"
      subtitle={`pattern tester · ${inWindow ? "selected window" : "all history"}`}
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
        <div className="field">
          <label>scan</label>
          <select value={form.scope} onChange={upd("scope")}>
            <option value="all">all history</option>
            <option value="window">selected window</option>
          </select>
        </div>
        <button className="btn" onClick={() => setSubmitted({ ...form })}>
          Run scan
        </button>
        <div className="stats-row" style={{ marginLeft: "auto" }}>
          <Stat label="events found" num={data?.n_events} format={(v) => `${Math.round(v)}`} fallbackValue="…" />
          <Stat
            label="win rate"
            num={t?.win_rate}
            format={(v) => `${(v * 100).toFixed(1)}%`}
            tone={t && t.win_rate >= 0.5 ? "up" : "down"}
          />
          <Stat
            label="mean outcome"
            num={t?.mean}
            format={(v) => `${(v * 100).toFixed(2)}%`}
            tone={t && t.mean >= 0 ? "up" : "down"}
          />
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
