import os
import csv
import io
import json
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Pulse — Garmin Dashboard")

# Data source: raw GitHub CSVs
DATA_REPO = os.environ.get(
    "DATA_REPO_URL",
    "https://raw.githubusercontent.com/zubednarova/app_data/main"
)

CSV_FILES = [
    "activities",
    "daily_summary",
    "sleep",
    "heart_rate_hrv",
    "stress_body_battery",
]

# In-memory cache
_cache: dict = {}


async def fetch_csv(name: str) -> list[dict]:
    """Fetch a CSV from GitHub and return as list of dicts."""
    if name in _cache:
        return _cache[name]
    url = f"{DATA_REPO}/{name}.csv"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    _cache[name] = rows
    return rows


@app.get("/api/data")
async def get_all_data():
    """Return all 5 CSV datasets as JSON."""
    result = {}
    for name in CSV_FILES:
        try:
            result[name] = await fetch_csv(name)
        except Exception as e:
            result[name] = {"error": str(e)}
    return JSONResponse(result)


@app.get("/api/data/{dataset}")
async def get_dataset(dataset: str):
    """Return a single CSV dataset as JSON."""
    if dataset not in CSV_FILES:
        return JSONResponse({"error": f"Unknown dataset: {dataset}"}, status_code=404)
    try:
        rows = await fetch_csv(dataset)
        return JSONResponse(rows)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/cache/clear")
async def clear_cache():
    """Clear the in-memory data cache."""
    _cache.clear()
    return JSONResponse({"status": "ok", "message": "Cache cleared"})


# Health check (Keboola POSTs to / on startup)
@app.api_route("/api/health", methods=["GET", "POST"])
async def health():
    return JSONResponse({"status": "ok"})


# Serve static files (the React build)
app.mount("/static", StaticFiles(directory="/app/static"), name="static")


# Catch-all: serve index.html for any non-API route (SPA routing)
@app.api_route("/{path:path}", methods=["GET", "POST"])
async def serve_spa(request: Request, path: str = ""):
    index_path = "/app/static/index.html"
    if os.path.exists(index_path):
        with open(index_path) as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Pulse Dashboard</h1><p>static/index.html not found. Build the frontend first.</p>")
