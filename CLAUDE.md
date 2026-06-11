# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) or other AI assistants when working with code in this repository.

## Project Overview

Undergraduate thesis (skripsi) — a Flask web application for Indonesian-language sentiment analysis using a fine-tuned IndoBERT model. Classifies text as **Positif / Netral / Negatif** (3 classes). The system has a two-service architecture that must both be running for the full feature set to work.

## Two-Service Architecture

| Service | Port | Entry Point | Framework |
|---------|------|-------------|-----------|
| Main web app | 5000 | `app.py` | Flask |
| Scraper microservice | 8000 | `scraper/main.py` | Flask + Playwright (async) |

Flask calls the scraper via HTTP (`httpx.post` to `http://127.0.0.1:8000/scrape`). The scraper service uses `asyncio` and `async_playwright` internally to scrape Twitter and Google News concurrently, but exposes a synchronous Flask HTTP interface.

## Setup & Running the App

All dependencies for both services are unified in a single `requirements.txt`.

```powershell
# Create and activate venv
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
python -m playwright install chromium
```

**Running Services:**
```powershell
# Terminal 1 — Flask scraper (port 8000)
python scraper/main.py

# Terminal 2 — Flask main app (port 5000)
python app.py
```

## Model Files (`models/`)

The trained model lives in `models/` and is loaded once at Flask startup. Required files:
- `config.json` — label mappings and model config
- `model.safetensors` — model weights (not excluded by `.gitignore`; `.bin`/`.pt`/`.h5` are)
- `tokenizer.json`, `tokenizer_config.json` — tokenizer

## Critical Architecture Details

**Threading & Async Background Tasks**:
Flask runs the orchestration pipeline in the background using `threading.Thread(daemon=True)`. This avoids the complexity of Celery/Redis for a simple local demo.
The scraper service uses `asyncio` and `async_playwright` internally. Do not introduce `selenium` or blocking WebDriver code into it.

**Data Storage**:
The pipeline stores state in an in-memory thread-safe dictionary (`_status_store` with a `threading.Lock()`).
Final results are persisted to disk as CSV files in the `data/` directory (e.g. `data/<request_id>.csv`).

**CSV Loading Optimization**:
We use `pandas.read_csv` with strict `dtype` definitions (`CSV_DTYPES`), selective `usecols`, and an in-memory caching layer (`_results_cache`) in `utils.py` to ensure dashboard loads stay under 3 seconds, even with 2,000+ row datasets.

**Preprocessing pipeline order** (`preprocessing.py`):
1. Remove URLs
2. Remove `@mentions`
3. Remove `#` symbol
4. Remove special characters (keep alphanumeric + spaces)
5. Case folding (lowercase)
6. Whitespace normalization

## Environment Variables (`.env`)

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=yourmail@gmail.com
SMTP_PASS=your_app_password
BASE_URL=http://localhost:5000
SCRAPER_URL=http://localhost:8000
```
