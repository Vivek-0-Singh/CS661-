export const COLORS = {
  bg: "#0b0e14",
  panel: "#141a23",
  panelHead: "#1b2330",
  grid: "#232c3a",
  border: "#26303f",
  text: "#c9d4e2",
  muted: "#7d8aa0",
  up: "#26a69a",
  down: "#ef5350",
  accent: "#58a6ff",
  bull: "#3fb950",
  bear: "#f85149",
};

export const ASSET_COLOR = {
  BTC: "#f7931a",
  ETH: "#627eea",
  BNB: "#f3ba2f",
  SOL: "#14f195",
  XRP: "#8faab8",
};

export function baseLayout(overrides = {}) {
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: COLORS.text, size: 11, family: "Inter, system-ui, sans-serif" },
    margin: { l: 48, r: 14, t: 22, b: 34 },
    xaxis: { gridcolor: COLORS.grid, zerolinecolor: COLORS.grid, automargin: true },
    yaxis: { gridcolor: COLORS.grid, zerolinecolor: COLORS.grid, automargin: true },
    showlegend: false,
    hovermode: "x unified",
    ...overrides,
  };
}

export const plotConfig = { displayModeBar: false, responsive: true };
