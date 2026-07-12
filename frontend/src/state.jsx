import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const Ctx = createContext(null);

export function AppStateProvider({ children }) {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [asset, setAsset] = useState("BTC");
  // Brushed time window shared across every view: { start, end } ISO strings.
  const [window, setWindow] = useState(null);
  // Pair selected in the correlation matrix for drill-down: [a, b] or null.
  const [pair, setPair] = useState(null);
  // Correlation view mode: "matrix" (heatmap) | "network" (node-link).
  const [corrView, setCorrView] = useState("matrix");
  // Trigger timestamps from the last What-If scan, drawn as markers on the
  // Time Machine detail chart (brush-and-link across views).
  const [events, setEvents] = useState([]);

  useEffect(() => {
    api
      .meta()
      .then((m) => {
        setMeta(m);
        if (m.default_window) setWindow(m.default_window);
        if (m.symbols?.length) setPair([m.symbols[0], m.symbols[1] ?? m.symbols[0]]);
      })
      .catch((e) => setError(e.message));
  }, []);

  const value = {
    meta, error, asset, setAsset, window, setWindow,
    pair, setPair, corrView, setCorrView, events, setEvents,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used within AppStateProvider");
  return ctx;
}
