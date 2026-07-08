import { useEffect, useRef, useState } from "react";
import { Plot } from "../plot.jsx";
import { Panel, Status } from "./ui.jsx";
import { useApp } from "../state.jsx";
import { api, WS_URL } from "../api";
import { useFetch } from "../hooks";
import { COLORS, baseLayout, plotConfig } from "../theme";

/**
 * View 2 — Market Depth Visualiser. Mirrored cumulative depth: buyer volume
 * (support) on the bid side, seller volume (resistance) on the ask side.
 * Live mode streams from the Binance relay; historical mode reconstructs depth
 * from OHLCV at the window end.
 */
export default function MarketDepth() {
  const { asset, window } = useApp();
  const [mode, setMode] = useState("historical");
  const [live, setLive] = useState(null);
  const [wsState, setWsState] = useState("idle");
  const wsRef = useRef(null);

  const hist = useFetch(
    () => api.depth({ symbol: asset, at: window.end }),
    [asset, window.end],
    mode === "historical"
  );

  useEffect(() => {
    if (mode !== "live") {
      wsRef.current?.close();
      return;
    }
    setWsState("connecting");
    let ws;
    try {
      ws = new WebSocket(WS_URL);
    } catch {
      setWsState("error");
      return;
    }
    wsRef.current = ws;
    ws.onopen = () => {
      setWsState("live");
      ws.send(JSON.stringify({ type: "subscribe", symbol: asset }));
    };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "depth") setLive(msg);
    };
    ws.onerror = () => setWsState("error");
    ws.onclose = () => setWsState((s) => (s === "live" ? "closed" : s));
    return () => ws.close();
  }, [mode, asset]);

  const book = mode === "live" ? live : hist.data;
  const bids = book?.bids ?? [];
  const asks = book?.asks ?? [];

  const fig = {
    data: [
      {
        type: "scatter",
        mode: "lines",
        x: bids.map((l) => l.price),
        y: bids.map((l) => l.cum),
        line: { color: COLORS.up, width: 1.5, shape: "hv" },
        fill: "tozeroy",
        fillcolor: "rgba(38,166,154,0.20)",
        name: "bids",
        hovertemplate: "bid $%{x:,.2f}<br>Σ %{y:,.1f}<extra></extra>",
      },
      {
        type: "scatter",
        mode: "lines",
        x: asks.map((l) => l.price),
        y: asks.map((l) => l.cum),
        line: { color: COLORS.down, width: 1.5, shape: "hv" },
        fill: "tozeroy",
        fillcolor: "rgba(239,83,80,0.20)",
        name: "asks",
        hovertemplate: "ask $%{x:,.2f}<br>Σ %{y:,.1f}<extra></extra>",
      },
    ],
    layout: baseLayout({
      height: 250,
      margin: { l: 50, r: 12, t: 8, b: 30 },
      xaxis: { title: { text: "price", font: { size: 10 } }, gridcolor: COLORS.grid, tickprefix: "$" },
      yaxis: { title: { text: "cumulative size", font: { size: 10 } }, gridcolor: COLORS.grid },
      shapes: book?.mid
        ? [
            {
              type: "line",
              x0: book.mid,
              x1: book.mid,
              y0: 0,
              y1: 1,
              yref: "paper",
              line: { color: COLORS.muted, width: 1, dash: "dot" },
            },
          ]
        : [],
    }),
  };

  const badge =
    mode === "live" ? (
      <span style={{ fontSize: 11, color: COLORS.muted }}>
        <span className="live-dot" /> {wsState}
      </span>
    ) : book?.synthetic ? (
      <span style={{ fontSize: 11, color: COLORS.muted }}>reconstructed</span>
    ) : null;

  return (
    <Panel
      className="span-2"
      title="Market Depth"
      subtitle={book?.mid ? `mid $${Number(book.mid).toLocaleString()}` : "order book"}
      actions={
        <div className="seg">
          <button className={mode === "historical" ? "active" : ""} onClick={() => setMode("historical")}>
            historical
          </button>
          <button className={mode === "live" ? "active" : ""} onClick={() => setMode("live")}>
            live
          </button>
        </div>
      }
    >
      {badge && <div style={{ textAlign: "right", marginBottom: 2 }}>{badge}</div>}
      <Status
        loading={mode === "historical" && hist.loading}
        error={mode === "historical" ? hist.error : null}
        empty={!book}
      >
        {mode === "live" && !live ? (
          <div className="status">
            {wsState === "error"
              ? "WS relay not reachable — start ws-server (npm start on :8080)."
              : "Connecting to live stream…"}
          </div>
        ) : (
          <Plot data={fig.data} layout={fig.layout} config={plotConfig} style={{ width: "100%" }} useResizeHandler />
        )}
      </Status>
    </Panel>
  );
}
