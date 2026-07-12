import { useEffect, useRef, useState } from "react";
import { Plot } from "../plot.jsx";
import { Panel, Status } from "./ui.jsx";
import { useApp } from "../state.jsx";
import { api } from "../api";
import { useFetch } from "../hooks";
import { COLORS, ASSET_COLOR, baseLayout, plotConfig } from "../theme";

/**
 * View 1 — The Time Machine: multi-resolution temporal explorer.
 * A compressed full-history overview with a range-slider brush drives the
 * shared window; the detail panel renders candlesticks + volume at the
 * auto-selected resolution, or at a manually forced one.
 *
 * Timestamps stay in Plotly's timezone-naive string space
 * ("YYYY-MM-DDTHH:mm:ss") end to end. Never round-trip through
 * Date.toISOString(): it converts to UTC, shifting the window by the local
 * UTC offset on every relayout event, which made the brush "run away" from
 * the pointer during drags.
 */
// Quick-zoom presets. The backend maps each resulting span to a readable
// candle resolution (5Y→monthly, 1Y→weekly, 1M→daily, 1W/1D→hourly).
const PRESETS = [
  { label: "5Y", days: 5 * 365 },
  { label: "1Y", days: 365 },
  { label: "1M", days: 30 },
  { label: "1W", days: 7 },
  { label: "1D", days: 1 },
];
const RES_LABEL = { "1mo": "monthly", "1w": "weekly", "1d": "daily", "1h": "hourly", "1m": "1-min" };

// Manual candle-resolution override (display-only: the stats panels keep
// their own capped auto-resolution). A button is enabled only when the
// current window yields a readable candle count (MIN..MAX); outside that the
// combo is either unreadable (<6 candles) or would freeze Plotly (>2000).
const RES_OPTIONS = [
  { key: "auto", label: "Auto" },
  { key: "1m", label: "1m", sec: 60 },
  { key: "1h", label: "1h", sec: 3600 },
  { key: "1d", label: "1d", sec: 86400 },
  { key: "1w", label: "1w", sec: 604800 },
  { key: "1mo", label: "1M", sec: 2629800 },
];
const MIN_CANDLES = 6;
const MAX_CANDLES = 2000;

const pad2 = (n) => String(n).padStart(2, "0");
// Format a Date from its local components — no UTC conversion.
const fmtNaive = (d) =>
  `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T` +
  `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
// Normalise Plotly/DB strings ("2020-08-14 03:22:11.4142") to "T" form.
const naive = (v) => String(v).replace(" ", "T");

export default function TimeMachine({ index = 0 }) {
  const { asset, meta, window, setWindow, events } = useApp();
  const cov = meta?.coverage?.find((c) => c.symbol === asset);

  const [res, setRes] = useState("auto");
  // Bumped on preset clicks so the overview's uirevision changes and Plotly
  // accepts the new prop-driven range even after a manual brush.
  const [rev, setRev] = useState(0);

  // Commit brush changes only after the drag pauses: re-rendering against an
  // in-progress drag fights the pointer, and every uncommitted tick would
  // otherwise refetch all four linked panels.
  const commitRef = useRef(null);
  useEffect(() => () => clearTimeout(commitRef.current), []);
  const queueWindow = (w) => {
    clearTimeout(commitRef.current);
    commitRef.current = setTimeout(() => setWindow(w), 250);
  };

  const spanSec = window
    ? (new Date(naive(window.end)) - new Date(naive(window.start))) / 1000
    : 0;
  const resEnabled = (o) =>
    o.key === "auto" || (spanSec / o.sec >= MIN_CANDLES && spanSec / o.sec <= MAX_CANDLES);

  // If a brush/preset makes the forced resolution unreadable, fall back to auto.
  useEffect(() => {
    const opt = RES_OPTIONS.find((o) => o.key === res);
    if (opt && !resEnabled(opt)) setRes("auto");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [window?.start, window?.end]);

  // Jump the shared window to the last `days` of available data.
  const applyPreset = (days) => {
    if (!cov) return;
    clearTimeout(commitRef.current);
    const end = new Date(naive(cov.end));
    const lo = new Date(naive(cov.start));
    const start = new Date(Math.max(lo.getTime(), end.getTime() - days * 86400000));
    setWindow({ start: fmtNaive(start), end: fmtNaive(end) });
    setRev((r) => r + 1);
  };

  const overview = useFetch(
    () => api.ohlcv({ symbol: asset, start: cov.start, end: cov.end, resolution: "1d" }),
    [asset, cov?.start, cov?.end],
    !!cov
  );

  const detail = useFetch(
    () => api.ohlcv({ symbol: asset, start: window.start, end: window.end, resolution: res }),
    [asset, window.start, window.end, res],
    !!window
  );

  const onRelayout = (e) => {
    if (e["xaxis.autorange"] && cov) {
      queueWindow({ start: naive(cov.start), end: naive(cov.end) });
      return;
    }
    const s = e["xaxis.range[0]"] ?? e["xaxis.range"]?.[0];
    const en = e["xaxis.range[1]"] ?? e["xaxis.range"]?.[1];
    // Pass Plotly's naive strings through untouched (no UTC round-trip).
    if (s && en) queueWindow({ start: naive(s), end: naive(en) });
  };

  const oc = overview.data?.candles ?? [];
  const color = ASSET_COLOR[asset] ?? COLORS.accent;
  const overviewFig = {
    data: [
      {
        type: "scatter",
        mode: "lines",
        x: oc.map((c) => c.ts),
        y: oc.map((c) => c.close),
        line: { color, width: 1.2 },
        fill: "tozeroy",
        fillcolor: color + "18",
        hovertemplate: "%{x|%b %Y}  $%{y:,.0f}<extra></extra>",
      },
    ],
    layout: baseLayout({
      height: 110,
      dragmode: false,
      uirevision: `${asset}:${rev}`,
      // Same left/right margins as the detail chart so both x-axes align.
      margin: { l: 54, r: 12, t: 4, b: 8 },
      xaxis: {
        type: "date",
        gridcolor: COLORS.grid,
        rangeslider: {
          visible: true,
          thickness: 0.45,
          bgcolor: COLORS.panelHead,
          bordercolor: COLORS.border,
          // Pin the mini-chart to full history so the handles always sit
          // under the dates they select.
          ...(cov ? { range: [naive(cov.start), naive(cov.end)] } : {}),
        },
        range: [window.start, window.end],
      },
      yaxis: { visible: false, fixedrange: true },
    }),
  };

  const dc = detail.data?.candles ?? [];

  // What-If trigger timestamps that fall inside the current window, drawn as
  // markers above the candles (linked view: the pattern scan annotates the
  // timeline).
  const t0 = new Date(naive(window.start)).getTime();
  const t1 = new Date(naive(window.end)).getTime();
  const evTs = (events ?? []).filter((t) => {
    const x = new Date(naive(t)).getTime();
    return x >= t0 && x <= t1;
  });
  const maxHigh = dc.length ? Math.max(...dc.map((c) => c.high)) : 0;

  const detailFig = {
    data: [
      {
        type: "candlestick",
        x: dc.map((c) => c.ts),
        open: dc.map((c) => c.open),
        high: dc.map((c) => c.high),
        low: dc.map((c) => c.low),
        close: dc.map((c) => c.close),
        increasing: { line: { color: COLORS.up } },
        decreasing: { line: { color: COLORS.down } },
        yaxis: "y",
      },
      {
        type: "bar",
        x: dc.map((c) => c.ts),
        y: dc.map((c) => c.volume),
        marker: {
          color: dc.map((c) =>
            c.close >= c.open ? "rgba(38,166,154,0.45)" : "rgba(239,83,80,0.45)"
          ),
        },
        yaxis: "y2",
      },
      ...(evTs.length && dc.length
        ? [
            {
              type: "scatter",
              mode: "markers",
              x: evTs,
              y: evTs.map(() => maxHigh * 1.02),
              marker: { symbol: "triangle-down", size: 7, color: "#9a6700" },
              name: "what-if trigger",
              hovertemplate: "What-If trigger  %{x|%b %d, %H:%M}<extra></extra>",
              yaxis: "y",
            },
          ]
        : []),
    ],
    layout: baseLayout({
      height: 384,
      uirevision: "detail",
      margin: { l: 54, r: 12, t: 4, b: 22 },
      xaxis: { type: "date", gridcolor: COLORS.grid, rangeslider: { visible: false } },
      yaxis: { domain: [0.24, 1], gridcolor: COLORS.grid, tickprefix: "$" },
      yaxis2: { domain: [0, 0.17], gridcolor: COLORS.grid },
    }),
  };

  return (
    <Panel
      index={index}
      className="span-6"
      title="The Time Machine"
      subtitle={`Temporal explorer · ${RES_LABEL[detail.data?.resolution] ?? "…"} candles · brush or use presets`}
      actions={
        <>
          <div className="seg">
            {PRESETS.map((p) => (
              <button key={p.label} onClick={() => applyPreset(p.days)} disabled={!cov}>
                {p.label}
              </button>
            ))}
          </div>
          <div className="seg">
            {RES_OPTIONS.map((o) => {
              const en = resEnabled(o);
              return (
                <button
                  key={o.key}
                  className={res === o.key ? "res-active" : en ? "res-on" : ""}
                  disabled={!en}
                  onClick={() => setRes(o.key)}
                  title={
                    en
                      ? `render ${o.label} candles`
                      : "not readable at this window size — brush a different range"
                  }
                >
                  {o.label}
                </button>
              );
            })}
          </div>
        </>
      }
    >
      <Status loading={overview.loading} error={overview.error}>
        <Plot
          data={overviewFig.data}
          layout={overviewFig.layout}
          config={plotConfig}
          onRelayout={onRelayout}
          style={{ width: "100%" }}
          useResizeHandler
        />
      </Status>
      <Status loading={detail.loading} error={detail.error} empty={dc.length === 0}>
        <Plot
          data={detailFig.data}
          layout={detailFig.layout}
          config={plotConfig}
          style={{ width: "100%" }}
          useResizeHandler
        />
      </Status>
    </Panel>
  );
}
