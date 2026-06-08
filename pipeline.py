import threading
import uuid
import httpx
import logging
from datetime import datetime
from pathlib import Path

from config import SCRAPER_BASE_URL, SCRAPER_ENDPOINT, SCRAPER_TIMEOUT
from inference import predict_batch
from preprocessing import preprocess_text
from utils import generate_csv_output, calculate_summary, send_notification

logger = logging.getLogger(__name__)

# State Store: memory dictionary protected by lock
_status_store = {}
_status_lock = threading.Lock()

# States
PENDING = "PENDING"
SCRAPING = "SCRAPING"
INFERENCING = "INFERENCING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def _update_status(req_id: str, status: str, message: str = "", progress: int = 0, **kwargs):
    with _status_lock:
        if req_id not in _status_store:
            _status_store[req_id] = {
                "id": req_id,
                "created_at": datetime.now().isoformat(),
            }
        _status_store[req_id].update({
            "status": status,
            "message": message,
            "progress": progress,
            "updated_at": datetime.now().isoformat(),
            **kwargs
        })

def get_status(req_id: str) -> dict:
    with _status_lock:
        return _status_store.get(req_id, {"status": "NOT_FOUND"})

def start_scrape_pipeline(keyword: str, limit: int, sources: list[str], mode: str = "demo") -> str:
    req_id = str(uuid.uuid4())
    _update_status(req_id, PENDING, "Mempersiapkan proses scraping...", 0, mode=mode)
    
    def _run():
        try:
            _update_status(req_id, SCRAPING, f"Sedang mengambil data untuk kata kunci '{keyword}'...", 10, mode=mode)

            scraper_url = f"{SCRAPER_BASE_URL}{SCRAPER_ENDPOINT}"
            try:
                response = httpx.post(
                    scraper_url,
                    json={"keyword": keyword, "limit": limit, "sources": sources},
                    timeout=SCRAPER_TIMEOUT,
                )
                response.raise_for_status()
            except httpx.ConnectError:
                logger.warning(f"Scraper tidak tersedia di {scraper_url} (ConnectError).")
                _update_status(
                    req_id, FAILED,
                    f"Layanan scraper tidak aktif. Pastikan server scraper berjalan di {SCRAPER_BASE_URL}.",
                    0
                )
                return
            except httpx.TimeoutException:
                logger.warning(f"Scraper timeout setelah {SCRAPER_TIMEOUT}s.")
                _update_status(
                    req_id, FAILED,
                    f"Scraper tidak merespons dalam {SCRAPER_TIMEOUT} detik. Coba kurangi jumlah data.",
                    0
                )
                return
            except httpx.HTTPStatusError as exc:
                logger.warning(f"Scraper HTTP error: {exc.response.status_code}")
                _update_status(
                    req_id, FAILED,
                    f"Scraper mengembalikan error {exc.response.status_code}.",
                    0
                )
                return

            scraper_data = response.json()

            if scraper_data.get("status") != "success":
                _update_status(req_id, FAILED, scraper_data.get("message", "Scraping gagal"), 0)
                return

            data = scraper_data.get("data", [])
            if not data:
                _update_status(req_id, COMPLETED, "Tidak ada data yang ditemukan", 100, total_results=0, file_path="")
                return

            _update_status(req_id, INFERENCING, "Menganalisis sentimen...", 50)

            raw_texts = [t.get("raw_text", "") for t in data]
            dates = [t.get("date", "") for t in data]
            sources_list = [t.get("source", "") for t in data]

            clean_texts = [preprocess_text(text) for text in raw_texts]
            predictions = predict_batch(clean_texts)

            results = []
            for raw, clean, date, src, pred in zip(raw_texts, clean_texts, dates, sources_list, predictions):
                results.append({
                    "raw_text": raw,
                    "clean_text": clean,
                    "date": date,
                    "source": src,
                    "predicted_label": pred.get("predicted_label", "Netral"),
                    "confidence_positive": pred.get("confidence_positive", 0.0),
                    "confidence_negative": pred.get("confidence_negative", 0.0),
                    "confidence_neutral": pred.get("confidence_neutral", 0.0),
                    "inference_time_ms": pred.get("inference_time_ms", 0.0),
                })

            csv_content = generate_csv_output(results)
            file_path = DATA_DIR / f"{req_id}.csv"
            with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(csv_content)

            summary = calculate_summary(results)

            _update_status(req_id, COMPLETED, "Selesai", 100,
                           total_results=len(results),
                           file_path=str(file_path),
                           summary=summary,
                           keyword=keyword)

        except Exception as e:
            logger.error(f"Pipeline error tidak terduga: {e}", exc_info=True)
            _update_status(req_id, FAILED, "Terjadi kesalahan tidak terduga saat memproses. Silakan coba lagi.", 0)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return req_id

def start_batch_pipeline(raw_texts: list[str]) -> str:
    req_id = str(uuid.uuid4())
    _update_status(req_id, PENDING, "Mempersiapkan data CSV...", 0)
    
    def _run():
        try:
            _update_status(req_id, INFERENCING, f"Memproses {len(raw_texts)} baris data...", 10)
            
            clean_texts = [preprocess_text(str(text).strip()) if str(text).strip() else "" for text in raw_texts]
            predictions = predict_batch(clean_texts)
            
            results = []
            for raw, clean, pred in zip(raw_texts, clean_texts, predictions):
                raw_str = str(raw).strip()
                is_empty = not raw_str or not clean
                if is_empty:
                    pred["skipped"] = True
                results.append({
                    "raw_text": raw_str,
                    "clean_text": clean,
                    "predicted_label": pred.get("predicted_label", "Netral"),
                    "confidence_positive": pred.get("confidence_positive", 0.0),
                    "confidence_negative": pred.get("confidence_negative", 0.0),
                    "confidence_neutral": pred.get("confidence_neutral", 0.0),
                    "inference_time_ms": pred.get("inference_time_ms", 0.0),
                    "skipped": pred.get("skipped", False),
                })
                
            csv_content = generate_csv_output(results)
            file_path = DATA_DIR / f"{req_id}.csv"
            with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(csv_content)
                
            summary = calculate_summary(results)
            
            _update_status(req_id, COMPLETED, "Selesai", 100, 
                           total_results=len(results), 
                           file_path=str(file_path),
                           summary=summary)
                           
        except Exception as e:
            logger.error(f"Batch Pipeline error: {e}", exc_info=True)
            _update_status(req_id, FAILED, f"Gagal memproses: {str(e)}", 0)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return req_id
