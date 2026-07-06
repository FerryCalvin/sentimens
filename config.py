# ============================================================
# config.py — Konfigurasi Aplikasi Flask
# ============================================================
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Base Paths ---
BASE_DIR = Path(__file__).parent.resolve()
MODEL_DIR = BASE_DIR / "models"

# --- Flask Config ---
SECRET_KEY = os.getenv("SECRET_KEY", "sentimens-indobert-skripsi-secret-key-2025")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB maks upload CSV (NFR-S-03)
DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"

# --- Model Config ---
MODEL_PATH = str(MODEL_DIR)
TOKENIZER_PATH = str(MODEL_DIR)
MAX_TOKEN_LENGTH = 512  # Max token BERT (FR-PP-08)

# --- Label Mapping (dari config.json model) ---
# LABEL_0 → Negatif, LABEL_1 → Netral, LABEL_2 → Positif
LABEL_MAP = {
    0: "Negatif",
    1: "Netral",
    2: "Positif",
}
LABEL_COLORS = {
    "Positif": "#28a745",   # Hijau (FR-VZ-05)
    "Negatif": "#dc3545",   # Merah (FR-VZ-05)
    "Netral":  "#6c757d",   # Abu-abu (FR-VZ-05)
}

# --- FastAPI Scraper Config ---
SCRAPER_BASE_URL = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000")
SCRAPER_ENDPOINT = "/scrape"
# FIX #1: Timeout diperbesar dari 60s → 300s
# Dual-scraping (Twitter + web search paralel) bisa butuh 60-120 detik.
# 300s = buffer aman agar pipeline tidak timeout sebelum scraper selesai.
# FIX #2: Dinaikkan ke 1800s — harus >= SCRAPE_COROUTINE_TIMEOUT scraper service
# (1500s), jika tidak client selalu menyerah duluan sebelum server selesai.
SCRAPER_TIMEOUT  = int(os.getenv("SCRAPER_TIMEOUT", "1800"))
DEFAULT_SCRAPE_LIMIT = int(os.getenv("SCRAPE_LIMIT", "500"))
DEFAULT_DAYS_BACK    = int(os.getenv("DAYS_BACK",    "365"))

# --- Batch Processing ---
BATCH_CHUNK_SIZE = 32  # Proses per-batch untuk efisiensi memori

# --- Inference Timeout (jaring pengaman untuk _predict_all) ---
INFERENCE_TIMEOUT_PER_ITEM_SEC = float(os.getenv("INFERENCE_TIMEOUT_PER_ITEM_SEC", "1.5"))
INFERENCE_TIMEOUT_MIN_SEC      = float(os.getenv("INFERENCE_TIMEOUT_MIN_SEC", "30"))
INFERENCE_TIMEOUT_MAX_SEC      = float(os.getenv("INFERENCE_TIMEOUT_MAX_SEC", "300"))

# --- Scraper history window ---
MAX_DAYS_BACK = int(os.getenv("MAX_DAYS_BACK", "365"))

# --- Kolom CSV Output (FR-BT-05) ---
CSV_OUTPUT_COLUMNS = [
    "teks_asli",
    "teks_bersih",
    "sentimen",
    "confidence_positif",
    "confidence_negatif",
    "confidence_netral",
    "source",
    "date",
]

# --- Model Evaluation Metrics (hasil testing model augmented pada test set, n=2173) ---
MODEL_METRICS = {
    "Accuracy":  91.62,
    "Precision": 91.10,
    "Recall":    91.41,
    "F1_Score":  91.24,
    "per_class": {
        "Negatif": {"precision": 92.32, "recall": 89.49, "f1": 90.88, "support": 752},
        "Netral":  {"precision": 87.41, "recall": 90.94, "f1": 89.14, "support": 519},
        "Positif": {"precision": 93.58, "recall": 93.79, "f1": 93.69, "support": 902},
    },
}

