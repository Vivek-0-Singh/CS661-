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
 * auto-selected resolution.
 */
export default function TimeMachine() {
  const { asset, meta, window, setWindow } = useApp();
  const cov = meta?.coverage?.find((c) => c.symbol === asset);

  const overview = useFetch(
    () => api.ohlcv({ symbol: asset, start: cov.start, end: cov.end, resolution: "1d" }),
    [asset, cov?.start, cov?.end],
    !!cov
  );

  const detail = useFetch(
    () => api.ohlcv({ symbol: asset, start: window.start, end: window.end, resolution: "auto" }),
    [asset, window.start, window.end],
    !!window
  );

  const onRelayout = (e) => {
    if (e["xaxis.autorange"] && cov) {
      setWindow({ start: cov.start, end: cov.end });
      return;
    }
    const s = e["xaxis.range[0]"] ?? e["xaxis.range"]?.[0];
    const en = e["xaxis.range[1]"] ?? e["xaxis.range"]?.[1];
    if (s && en) {
      setWindow({ start: new Date(s).toISOString(), end: new Date(en).toISOString() });
    }
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
      height: 120,
      dragmode: false,
      uirevision: asset,
      margin: { l: 10, r: 10, t: 6, b: 8 },
      xaxis: {
        type: "date",
        gridcolor: COLORS.grid,
        rangeslider: { visible: true, thickness: 0.5, bgcolor: "#0d131c", bordercolor: COLORS.border },
        range: [window.start, window.end],
      },
      yaxis: { visible: false, fixedrange: true },
    }),
  };

  const dc = detail.data?.candles ?? [];
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
    ],
    layout: baseLayout({
      height: 300,
      uirevision: "detail",
      margin: { l: 54, r: 12, t: 8, b: 26 },
      xaxis: { type: "date", gridcolor: COLORS.grid, rangeslider: { visible: false } },
      yaxis: { domain: [0.24, 1], gridcolor: COLORS.grid, tickprefix: "$" },
      yaxis2: { domain: [0, 0.17], gridcolor: COLORS.grid },
    }),
  };

  return (
    <Panel
      className="span-6"
      title="The Time Machine"
      subtitle={`Temporal explorer · ${detail.data?.resolution ?? "…"} candles · drag the slider to brush every view`}
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
