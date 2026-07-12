// Light theme. Candle up/down keep the industry-standard green/red
// (TradingView palette — legible on white); all text/UI colours are chosen
// for WCAG-AA contrast on a white panel.
export const COLORS = {
  bg: "#f4f6fa",
  panel: "#ffffff",
  panelHead: "#f1f4f8",
  grid: "#eaeef4",
  border: "#dbe2ea",
  text: "#1c2733",
  muted: "#5d6c7b",
  up: "#26a69a",
  down: "#ef5350",
  accent: "#0969da",
  bull: "#1a7f37",
  bear: "#cf222e",
  warn: "#9a6700",
};

// Brand-recognisable but tuned for contrast against white.
export const ASSET_COLOR = {
  BTC: "#f7931a",
  ETH: "#627eea",
  BNB: "#c99400",
  SOL: "#9945ff",
  XRP: "#546e7a",
};

// Text colour that stays readable on top of each asset chip.
export const ASSET_TAB_TEXT = {
  BTC: "#1c2733",
  ETH: "#ffffff",
  BNB: "#1c2733",
  SOL: "#ffffff",
  XRP: "#ffffff",
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
    hoverlabel: {
      bgcolor: "#ffffff",
      bordercolor: COLORS.border,
      font: { color: COLORS.text, size: 11 },
    },
    ...overrides,
  };
}

export const plotConfig = { displayModeBar: false, responsive: true };
