// In production (Vercel) set VITE_API_BASE to the Render backend, e.g.
// "https://cryptolens-api.onrender.com/api". Locally it falls back to the
// Vite dev proxy at "/api".
const BASE = import.meta.env.VITE_API_BASE || "/api";

async function get(path, params = {}) {
  const entries = Object.entries(params).filter(([, v]) => v != null && v !== "");
  const qs = new URLSearchParams(entries).toString();
  const res = await fetch(`${BASE}${path}${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  meta: () => get("/meta"),
  ohlcv: (p) => get("/ohlcv", p),
  volatility: (p) => get("/volatility", p),
  correlation: (p) => get("/correlation", p),
  correlationPair: (p) => get("/correlation/pair", p),
  patterns: (p) => get("/patterns", p),
  depth: (p) => get("/depth", p),
};

// In production set VITE_WS_URL to the Render ws-server over TLS, e.g.
// "wss://cryptolens-ws.onrender.com".
export const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8080";
