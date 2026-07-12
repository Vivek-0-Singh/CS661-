import { useEffect, useRef, useState } from "react";
import { Plot } from "../plot.jsx";
import { Panel, Status } from "./ui.jsx";
import { TickPulse } from "../fx/TickPulse.jsx";
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
export default function MarketDepth({ index = 0 }) {
  const { asset, window } = useApp();
  const [mode, setMode] = useState("historical");
  const [live, setLive] = useState(null);
  const [wsState, setWsState] = useState("idle");
  // How many connect attempts since the last successful open — drives the
  // "waking the relay" hint (Render's free tier cold-starts in ~30–60s).
  const [attempts, setAttempts] = useState(0);
  const wsRef = useRef(null);

  const hist = useFetch(
    () => api.depth({ symbol: asset, at: window.end }),
    [asset, window.end],
    mode === "historical"
  );

  // Live mode with auto-reconnect + exponential backoff. Without this a single
  // failed connect (relay asleep on the free tier, a dropped socket, a Wi-Fi
  // blip) left the panel stuck forever — the relay itself is fine, the client
  // just never tried again.
  useEffect(() => {
    if (mode !== "live") return;

    let ws = null;
    let tries = 0;
    let retryTimer = null;
    let disposed = false;

    const scheduleReconnect = () => {
      if (disposed) return;
      const delay = Math.min(1000 * 2 ** tries, 15000); // 1,2,4,8,15s (capped)
      tries += 1;
      setAttempts(tries);
      retryTimer = setTimeout(open, delay);
    };

    const open = () => {
      if (disposed) return;
      setWsState((s) => (s === "live" ? "reconnecting" : tries === 0 ? "connecting" : "reconnecting"));
      try {
        ws = new WebSocket(WS_URL);
      } catch {
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;
      ws.onopen = () => {
        tries = 0;
        setAttempts(0);
        setWsState("live");
        ws.send(JSON.stringify({ type: "subscribe", symbol: asset }));
      };
      ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch { return; }
        if (msg.type === "depth") setLive(msg);
        // Relay tells us its Binance upstream is down (e.g. geo-block): show a
        // clear message instead of a hopeful spinner.
        else if (msg.type === "status" && msg.ok === false) setWsState("unavailable");
      };
      ws.onerror = () => { /* onclose fires next and drives the retry */ };
      ws.onclose = () => { if (!disposed) scheduleReconnect(); };
    };

    open();
    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      ws?.close();
    };
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
      height: 252,
      margin: { l: 50, r: 12, t: 6, b: 30 },
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
        <TickPulse mid={live?.mid} /> <span className="live-dot" /> {wsState}
      </span>
    ) : book?.synthetic ? (
      <span style={{ fontSize: 11, color: COLORS.warn }}>synthetic (reconstructed) — not real quotes</span>
    ) : null;

  return (
    <Panel
      index={index}
      glow={mode === "live" && wsState === "live" ? "ok" : undefined}
      className="span-3"
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
        empty={mode === "historical" && !book}
      >
        {mode === "live" && !live ? (
          <div className="status">
            {wsState === "unavailable"
              ? "Live feed unavailable — the relay can't reach Binance right now."
              : attempts >= 2
              ? "Waking the live relay (free tier cold-starts in ~30–60s)…"
              : "Connecting to live stream…"}
          </div>
        ) : (
          <Plot data={fig.data} layout={fig.layout} config={plotConfig} style={{ width: "100%" }} useResizeHandler />
        )}
      </Status>
    </Panel>
  );
}
