# Launch the full CryptoLens stack, each service in its own PowerShell window.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1
$root = Split-Path $PSScriptRoot -Parent

# 1) Backend REST API (FastAPI on :8000)
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "`$env:PYTHONPATH='$root\backend'; & '$root\backend\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --port 8000"

# 2) WebSocket relay for live order book (:8080)
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "`$env:PORT='8080'; node '$root\ws-server\server.js'"

# 3) Frontend (Vite on :5173)
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "npm --prefix '$root\frontend' run dev"

Write-Host "Started backend (:8000), ws-relay (:8080), frontend (:5173)." -ForegroundColor Green
Write-Host "If the DB is empty, run ingestion first:" -ForegroundColor Yellow
Write-Host "  `$env:PYTHONPATH='$root\backend'; & '$root\backend\.venv\Scripts\python.exe' -m ingestion.download --start 2024-01 --end 2024-03"
