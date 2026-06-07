# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Undergraduate thesis (skripsi) — a Flask web application for Indonesian-language sentiment analysis using a fine-tuned IndoBERT model. Classifies text as **Positif / Netral / Negatif** (3 classes). The system has a two-service architecture that must both be running for the full feature set to work.

## Two-Service Architecture

| Service | Port | Entry Point | Framework |
|---------|------|-------------|-----------|
| Main web app | 5000 | `app.py` | Flask |
| Scraper microservice | 8000 | `scraper/main.py` | FastAPI + Playwright |

Flask calls the scraper via HTTP (`httpx.post` to `http://127.0.0.1:8000/scrape`). The FastAPI service only accepts connections from `localhost:5000` (CORS restriction). FastAPI docs are available at `http://localhost:8000/docs` when running.

## Running the App

**Both services at once (Windows):**
```bat
run_all.bat
```

**Individually:**
```powershell
# Terminal 1 — FastAPI scraper
cd scraper
python main.py          # runs on port 8000

# Terminal 2 — Flask main app
python app.py           # runs on port 5000
```

**Flask health check:** `GET http://localhost:5000/api/health`

## Setup

Two separate `requirements.txt` files — one per service:

```powershell
# Create and activate venv
python -m venv venv
venv\Scripts\activate

# Install main app dependencies
pip install -r requirements.txt

# Install scraper dependencies
pip install -r scraper/requirements.txt

# Install Playwright browsers (required for scraper)
playwright install chromium
```

## Model Files (`models/`)

The trained model lives in `models/` and is loaded once at Flask startup. Required files:
- `config.json` — label mappings and model config
- `model.safetensors` — model weights (not excluded by `.gitignore`; `.bin`/`.pt`/`.h5` are)
- `tokenizer.json`, `tokenizer_config.json` — tokenizer

`app.py` sets `use_reloader=False` so the model isn't loaded twice during development. If `models/` is missing or corrupt, Flask starts but `MODEL_LOADED = False` and all routes that need inference will redirect with a flash error.

## Training

To re-train the model from scratch (outputs to `models/`):

```powershell
cd training
python train.py --epochs 3 --batch_size 16 --lr 2e-5

# With a custom Kaggle CSV dataset
python train.py --epochs 3 --batch_size 16 --lr 2e-5 --kaggle_csv path/to/reviews.csv
```

Training expects CSV datasets for IndoNLU SmSA and NusaX-Senti to be available (see `training/data_loader.py`). Training log is written to `training/training_log.txt`.

## Critical Architecture Details

**Label index mapping** (hardcoded in `config.py` and `inference.py`):
- Index 0 → Negatif
- Index 1 → Netral
- Index 2 → Positif

This mapping must stay consistent between training (`training/data_loader.py: LABEL2ID/ID2LABEL`) and inference (`inference.py: probs_list[0/1/2]`).

**Preprocessing pipeline order** (`preprocessing.py`) — order is strict, changing it affects results:
1. Remove URLs
2. Remove `@mentions`
3. Remove `#` symbol (keep word)
4. Remove special characters (keep alphanumeric + spaces)
5. Case folding (lowercase)
6. Whitespace normalization

No stopword removal during inference — BERT needs full sentence context. Stopwords are only filtered in `get_word_frequencies()` (word cloud only).

**Batch inference** (`inference.py:predict_batch`) uses `batch_size=32`, padding all texts in each chunk to the same length for efficiency.

**Session state** — all analysis results (batch CSV, scrape results, dashboard data) are stored in Flask's server-side session. The app is stateless across restarts; there is no database.

## Flask Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Home — single text analysis form |
| POST | `/analyze` | Run single-text inference |
| GET/POST | `/batch` | CSV upload and batch analysis |
| GET | `/download` | Download batch results as CSV |
| GET/POST | `/scrape` | Live Twitter scraping + analysis |
| GET | `/dashboard` | Visualisation dashboard (requires prior scrape) |
| GET | `/api/health` | Health check JSON |

## Environment Variables (`.env`)

```
SECRET_KEY=            # Flask secret key (has insecure default for dev)
FLASK_DEBUG=           # "true" to enable debug mode
SCRAPER_BASE_URL=      # default: http://127.0.0.1:8000
```
