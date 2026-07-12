import { useApp } from "./state.jsx";
import { ASSET_COLOR, ASSET_TAB_TEXT } from "./theme";
import TimeMachine from "./components/TimeMachine.jsx";
import VolatilityEngine from "./components/VolatilityEngine.jsx";
import CorrelationMatrix from "./components/CorrelationMatrix.jsx";
import MarketDepth from "./components/MarketDepth.jsx";
import WhatIfSimulator from "./components/WhatIfSimulator.jsx";

const fmt = (s) =>
  s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";

function Header() {
  const { meta, asset, setAsset, window } = useApp();
  const symbols = meta?.symbols ?? ["BTC", "ETH", "BNB", "SOL", "XRP"];
  const covered = new Set((meta?.coverage ?? []).filter((c) => c.rows > 0).map((c) => c.symbol));
  return (
    <header className="app-header">
      <div className="brand">
        <h1>
          Crypto<span className="lens">Lens</span>
        </h1>
        <span className="tag">Interactive Financial Market Intelligence</span>
      </div>
      <div className="asset-tabs">
        {symbols.map((s) => {
          const active = s === asset;
          const disabled = meta && !covered.has(s);
          return (
            <button
              key={s}
              className={`asset-tab ${active ? "active" : ""}`}
              style={active ? { background: ASSET_COLOR[s], color: ASSET_TAB_TEXT[s] } : {}}
              disabled={disabled}
              title={disabled ? "no data ingested for this asset" : ""}
              onClick={() => setAsset(s)}
            >
              {s}
            </button>
          );
        })}
      </div>
      <div className="window-readout">
        Selected window
        <br />
        <b>{fmt(window?.start)}</b> → <b>{fmt(window?.end)}</b>
      </div>
    </header>
  );
}

export default function App() {
  const { error, window } = useApp();

  if (error) {
    return (
      <>
        <Header />
        <div className="status err" style={{ marginTop: 40 }}>
          Cannot reach the API: {error}
          <br />
          Start the backend (uvicorn on :8000) and ingest data first.
        </div>
      </>
    );
  }

  return (
    <>
      <Header />
      {!window ? (
        <div className="status">Loading dataset…</div>
      ) : (
        // No key={asset} remount: switching assets updates each view in place,
        // so panel-local state (depth mode, scenario, what-if form) survives
        // and asset-independent views (correlation) don't refetch needlessly.
        <main className="dashboard">
          <TimeMachine index={0} />
          <VolatilityEngine index={1} />
          <CorrelationMatrix index={2} />
          <MarketDepth index={3} />
          <WhatIfSimulator index={4} />
        </main>
      )}
    </>
  );
}
