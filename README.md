# CryptoLens

An interactive visual analytics system for crypto market intelligence — CS661 Group-13.

Five coordinated, brushable views over 5 years of minute-level data for BTC, ETH, BNB, SOL, XRP:

1. **The Time Machine** — multi-resolution temporal explorer (brush & link).
2. **Market Depth Visualiser** — order-book depth (live via WebSocket + historical reconstruction).
3. **The What-If Simulator** — pattern hypothesis tester over all history.
4. **Volatility Engine** — market-risk analytics with normal / stress / crash scenarios.
5. **Cross-Asset Correlation Matrix** — pairwise correlation heatmap with drill-down.

## Architecture

```
CryptoLens/
├─ backend/            FastAPI REST API + statistics (Python)
│  ├─ app/             API app, DuckDB store, stats engine
│  └─ ingestion/       Binance data.binance.vision downloader → DuckDB
├─ ws-server/          Node + ws relay for live Binance order book
├─ frontend/           React + Vite + Plotly/D3 single-page UI
└─ data/               DuckDB database + downloaded parquet (git-ignored)
```

## Tech notes

- **Storage:** DuckDB (embedded, columnar, Parquet-native). Chosen over Postgres/TimescaleDB
  so the whole stack runs with zero DB-server setup while still handling ~10.5M rows fast.
  The access layer is plain SQL, so a later swap to TimescaleDB is mechanical.
- Data source: public `data.binance.vision` monthly 1m klines (no API key needed).
- Live order book: public `wss://stream.binance.com:9443` depth stream (no auth).

## Quick start

### 1. Backend + data
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Download a small sample (fast) to get running:
python -m ingestion.download --start 2024-01 --end 2024-03 --symbols BTC ETH

# ...or the full 5-year dataset (large, slow):
# python -m ingestion.download --start 2020-01 --end 2024-12

# Run the API
uvicorn app.main:app --reload --port 8000
```

### 2. WebSocket relay (live order book)
```powershell
cd ws-server
npm install
npm start        # ws://localhost:8080
```

### 3. Frontend
```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173
```
