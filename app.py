import os
import csv
import json

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Pulse — Garmin Dashboard")

# Keboola input mapping places files here
DATA_DIR = "/data/in/tables"

CSV_FILES = {
    "activities": "activities.csv",
    "daily_summary": "daily_summary.csv",
    "sleep": "sleep.csv",
    "heart_rate_hrv": "heart_rate_hrv.csv",
    "stress_body_battery": "stress_body_battery.csv",
}

# In-memory cache
_cache: dict = {}


def read_csv(name: str) -> list[dict]:
    """Read a CSV from Keboola input mapping."""
    if name in _cache:
        return _cache[name]

    filename = CSV_FILES.get(name)
    if not filename:
        raise ValueError(f"Unknown dataset: {name}")

    filepath = os.path.join(DATA_DIR, filename)

    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"{filepath} not found. "
            f"Check Input Mapping: table in.c-zbe_garmin.{name} -> {filename}"
        )

    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    _cache[name] = rows
    return rows


@app.get("/api/data")
async def get_all_data():
    """Return all 5 CSV datasets as JSON."""
    result = {}
    for name in CSV_FILES:
        try:
            result[name] = read_csv(name)
        except Exception as e:
            result[name] = {"error": str(e)}
    return JSONResponse(result)


@app.get("/api/data/{dataset}")
async def get_dataset(dataset: str):
    """Return a single CSV dataset as JSON."""
    if dataset not in CSV_FILES:
        return JSONResponse({"error": f"Unknown dataset: {dataset}"}, status_code=404)
    try:
        rows = read_csv(dataset)
        return JSONResponse(rows)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/cache/clear")
async def clear_cache():
    """Clear the in-memory data cache."""
    _cache.clear()
    return JSONResponse({"status": "ok", "message": "Cache cleared"})


@app.get("/api/debug")
async def debug_info():
    """Show what files exist in /data/in/tables/ for troubleshooting."""
    files = []
    if os.path.exists(DATA_DIR):
        files = os.listdir(DATA_DIR)
    return JSONResponse({
        "data_dir": DATA_DIR,
        "exists": os.path.exists(DATA_DIR),
        "files": files,
        "expected": list(CSV_FILES.values()),
    })


# Health check (Keboola POSTs to / on startup)
@app.api_route("/api/health", methods=["GET", "POST"])
async def health():
    return JSONResponse({"status": "ok"})


# Serve static files
app.mount("/static", StaticFiles(directory="/app/static"), name="static")


# Catch-all: serve index.html for any non-API route
@app.api_route("/{path:path}", methods=["GET", "POST"])
async def serve_spa(request: Request, path: str = ""):
    index_path = "/app/static/index.html"
    if os.path.exists(index_path):
        with open(index_path) as f:
            return HTMLResponse(f.read())
    return HTMLResponse(
        "<h1>Pulse Dashboard</h1><p>static/index.html not found.</p>"
    )
