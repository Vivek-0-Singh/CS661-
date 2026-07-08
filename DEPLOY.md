# Deploying CryptoLens

The stack is split across two hosts because Vercel can't run persistent
WebSocket servers or bundle a large database:

| Service | Host | Why |
|---|---|---|
| `frontend` | **Vercel** | Static Vite SPA — ideal for Vercel. |
| `backend` (FastAPI + DuckDB) | **Render** | Long-running process; data baked in at build time. |
| `ws-server` (live order book) | **Render** | Needs a persistent WebSocket connection to Binance. |

You need the code on GitHub first (`git init`, push).

---

## 1. Backend + WebSocket relay → Render

Both services are defined in [`render.yaml`](render.yaml).

1. Render Dashboard → **New → Blueprint** → connect this GitHub repo.
2. Render reads `render.yaml` and creates **`cryptolens-api`** and
   **`cryptolens-ws`**. Click **Apply**.
3. First build of `cryptolens-api` runs the ingestion (default: Jan–Mar 2024,
   all 5 assets) and bakes the DuckDB file into the deploy. To load more
   history, edit the `INGEST_START` / `INGEST_END` env vars (longer builds).
4. When both are live, copy their URLs, e.g.:
   - API: `https://cryptolens-api.onrender.com`
   - WS:  `https://cryptolens-ws.onrender.com` → use as `wss://cryptolens-ws.onrender.com`

> Free-tier Render services sleep after ~15 min idle; the first request cold-starts (~30–60 s).

Sanity-check the API: open `https://cryptolens-api.onrender.com/api/health` → `{"status":"ok"}`.

---

## 2. Frontend → Vercel

1. Vercel → **Add New → Project** → import this repo.
2. The root [`vercel.json`](vercel.json) builds `frontend/` and outputs
   `frontend/dist` — no need to touch the multi-service prompt.
3. Add **Environment Variables** (Project → Settings → Environment Variables),
   using your Render URLs from step 1:

   | Name | Value |
   |---|---|
   | `VITE_API_BASE` | `https://cryptolens-api.onrender.com/api` |
   | `VITE_WS_URL` | `wss://cryptolens-ws.onrender.com` |

   These are read at **build time**, so redeploy after adding them.
4. Deploy. The frontend calls the Render API cross-origin (the backend ships
   with `CORS_ORIGINS=*`; lock it to your Vercel URL later if you want).

---

## Notes
- To lock CORS down: set `CORS_ORIGINS=https://<your-app>.vercel.app` on the
  Render `cryptolens-api` service.
- Local dev is unchanged: leave the two `VITE_*` vars unset and run
  `scripts/start-all.ps1` — the app falls back to the Vite proxy and
  `ws://localhost:8080`.
