import { Plot } from "../plot.jsx";
import { Panel, Status } from "./ui.jsx";
import { useApp } from "../state.jsx";
import { api } from "../api";
import { useFetch } from "../hooks";
import { COLORS, baseLayout, plotConfig } from "../theme";

/**
 * View 5 — Cross-Asset Correlation Matrix. Always shows all five assets
 * regardless of the selected one. Clicking a cell drills into the rolling
 * correlation for that pair.
 */
export default function CorrelationMatrix() {
  const { window, pair, setPair } = useApp();

  const matrix = useFetch(
    () => api.correlation({ start: window.start, end: window.end, resolution: "auto" }),
    [window.start, window.end]
  );

  const drill = useFetch(
    () =>
      api.correlationPair({
        a: pair[0],
        b: pair[1],
        start: window.start,
        end: window.end,
        resolution: "auto",
        window: 30,
      }),
    [pair?.[0], pair?.[1], window.start, window.end],
    !!pair && pair[0] !== pair[1]
  );

  const labels = matrix.data?.labels ?? [];
  const z = matrix.data?.matrix ?? [];

  const annotations = [];
  labels.forEach((_, i) =>
    labels.forEach((__, j) => {
      const v = z[i]?.[j];
      annotations.push({
        x: labels[j],
        y: labels[i],
        text: v == null ? "—" : v.toFixed(2),
        showarrow: false,
        font: { size: 11, color: v != null && Math.abs(v) > 0.6 ? "#0b0e14" : COLORS.text },
      });
    })
  );

  const heatFig = {
    data: [
      {
        type: "heatmap",
        z,
        x: labels,
        y: labels,
        zmin: -1,
        zmax: 1,
        colorscale: "RdBu",
        reversescale: true,
        showscale: false,
        xgap: 3,
        ygap: 3,
        hovertemplate: "%{y} · %{x}: %{z:.2f}<extra></extra>",
      },
    ],
    layout: baseLayout({
      height: 210,
      margin: { l: 44, r: 10, t: 8, b: 30 },
      annotations,
      xaxis: { side: "bottom", gridcolor: "rgba(0,0,0,0)" },
      yaxis: { autorange: "reversed", gridcolor: "rgba(0,0,0,0)" },
    }),
  };

  const series = drill.data?.series ?? [];
  const drillFig = {
    data: [
      {
        type: "scatter",
        mode: "lines",
        x: series.map((s) => s.ts),
        y: series.map((s) => s.corr),
        line: { color: COLORS.accent, width: 1.5 },
        fill: "tozeroy",
        fillcolor: "rgba(88,166,255,0.10)",
        hovertemplate: "%{x|%b %d}  ρ=%{y:.2f}<extra></extra>",
      },
    ],
    layout: baseLayout({
      height: 120,
      margin: { l: 44, r: 10, t: 6, b: 24 },
      xaxis: { type: "date", gridcolor: COLORS.grid },
      yaxis: { range: [-1, 1], gridcolor: COLORS.grid, zeroline: true, zerolinecolor: COLORS.border },
    }),
  };

  return (
    <Panel
      className="span-2"
      title="Correlation Matrix"
      subtitle={matrix.data ? `${matrix.data.resolution} returns · all assets` : "cross-asset"}
    >
      <Status loading={matrix.loading} error={matrix.error} empty={labels.length === 0}>
        <Plot
          data={heatFig.data}
          layout={heatFig.layout}
          config={plotConfig}
          style={{ width: "100%" }}
          useResizeHandler
          onClick={(e) => {
            const p = e.points?.[0];
            if (p) setPair([p.y, p.x]);
          }}
        />
        {pair && pair[0] !== pair[1] && (
          <>
            <div style={{ color: COLORS.muted, fontSize: 11, margin: "6px 0 2px" }}>
              {pair[0]} · {pair[1]} rolling ρ ·{" "}
              <b style={{ color: COLORS.text }}>
                overall {drill.data?.overall != null ? drill.data.overall.toFixed(2) : "…"}
              </b>
            </div>
            <Status loading={drill.loading} error={drill.error} empty={series.length === 0}>
              <Plot data={drillFig.data} layout={drillFig.layout} config={plotConfig} style={{ width: "100%" }} useResizeHandler />
            </Status>
          </>
        )}
      </Status>
    </Panel>
  );
}
