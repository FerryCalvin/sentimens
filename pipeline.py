import threading
import uuid
import httpx
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
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
FINALIZING = "FINALIZING"
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


def _scrape_via_subprocess(keyword: str, limit: int) -> list:
    """
    Jalankan scraper_worker.py sebagai subprocess terpisah.
    Playwright butuh proses clean — tidak bisa spawn dari Flask thread.

    FIX #2 — Windows Encoding:
      Tambahkan encoding='utf-8' + errors='replace' agar tidak crash
      saat output mengandung emoji atau karakter non-cp1252 (byte 0x9d, dll.)
    """
    import subprocess
    import sys
    import os
    import json as _json

    worker = os.path.join(os.path.dirname(__file__), "scraper_worker.py")
    python = sys.executable

    # Set PYTHONIOENCODING via env agar child process juga pakai UTF-8
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"]       = "1"   # Python 3.7+ UTF-8 mode

    try:
        result = subprocess.run(
            [python, worker, keyword, str(limit)],
            capture_output=True,
            text=True,
            encoding="utf-8",    # FIX #2: paksa UTF-8, bukan cp1252
            errors="replace",    # FIX #2: karakter invalid diganti '?', tidak crash
            timeout=300,         # FIX #1: diperpanjang dari 90s → 300s
            cwd=os.path.dirname(__file__),
            env=env,
        )
        if result.returncode != 0:
            logger.warning(f"[Worker] stderr: {result.stderr[:400]}")

        stdout = result.stdout.strip() if result.stdout else ""
        if stdout:
            return _json.loads(stdout)
        return []
    except subprocess.TimeoutExpired:
        logger.error("[Worker] Subprocess timeout (300s)")
        return []
    except Exception as e:
        logger.error(f"[Worker] Subprocess error: {e}")
        return []


def _scrape_in_process(keyword: str, limit: int, sources: list, req_id: str = None) -> list:
    """
    Scrape menggunakan subprocess worker terpisah per source.
    """
    results = []
    limit_per_source = max(5, limit // max(len(sources), 1))

    need_twitter = "twitter" in sources
    need_web = "web" in sources or "news" in sources

    if need_twitter or need_web:
        total_sources = (1 if need_twitter else 0) + (1 if need_web else 0)
        fetch_limit = limit_per_source * total_sources
        logger.info(f"[Pipeline] Web search via subprocess: {keyword} | limit={fetch_limit}")
        all_data = _scrape_via_subprocess(keyword, fetch_limit)
        logger.info(f"[Pipeline] Subprocess: {len(all_data)} hasil total")

        if need_twitter and need_web:
            mid = len(all_data) // 2
            twitter_data = all_data[:mid]
            web_data = all_data[mid:]
        elif need_twitter:
            twitter_data = all_data
            web_data = []
        else:
            twitter_data = []
            web_data = all_data

        if need_twitter:
            for item in twitter_data:
                item["source"] = "twitter"
            results.extend(twitter_data)
            logger.info(f"[Pipeline] Social (relabeled): {len(twitter_data)} hasil")
            if req_id:
                _update_status(req_id, SCRAPING, f"Data sosial selesai ({len(twitter_data)} item), menyusun data...", 25)

        if need_web:
            results.extend(web_data)
            logger.info(f"[Pipeline] Web: {len(web_data)} hasil")
            if req_id:
                _update_status(req_id, SCRAPING, f"Data web selesai ({len(web_data)} item), menyusun data...", 40)

    # Deduplicate
    seen = set()
    unique = []
    for item in results:
        t = item.get("raw_text", "")[:80]
        if t and t not in seen:
            seen.add(t)
            unique.append(item)

    return unique[:limit]


def start_scrape_pipeline(keyword: str, limit: int, sources: list[str], mode: str = "demo", days_back: int = 7) -> str:
    req_id = str(uuid.uuid4())
    _update_status(req_id, PENDING, "Mempersiapkan proses scraping...", 0, mode=mode)
    
    def _run():
        try:
            _update_status(req_id, SCRAPING, f"Sedang mengambil data untuk kata kunci '{keyword}'...", 10, mode=mode)

            # ── FIX #1: timeout diperbesar ── httpx default 10s terlalu cepat
            # Scraping butuh ~60-120 detik (Twitter + web search paralel)
            # Pakai timeout dari config (SCRAPER_TIMEOUT = 300s)
            try:
                scraper_url = f"{SCRAPER_BASE_URL}{SCRAPER_ENDPOINT}"
                response = httpx.post(
                    scraper_url,
                    json={"keyword": keyword, "limit": limit, "sources": sources, "days_back": days_back},
                    timeout=httpx.Timeout(
                        connect=10.0,   # Koneksi awal cepat (scraper harus sudah jalan)
                        read=300.0,     # FIX #1: Tunggu 5 menit untuk scraping selesai
                        write=10.0,
                        pool=5.0,
                    ),
                )
                response.raise_for_status()
                scraper_data = response.json()
                if scraper_data.get("status") == "success":
                    data = scraper_data.get("data", [])
                    logger.info(f"[Pipeline] Scraper eksternal: {len(data)} hasil")
            except Exception as ext_err:
                logger.warning(f"[Pipeline] Scraper eksternal tidak tersedia ({ext_err}), pakai in-process scraping")
                data = _scrape_in_process(keyword, limit, sources, req_id=req_id)

            # ── FIX #3: Graceful handling jika 0 hasil ────────────────────
            # Jangan crash — buat file CSV kosong agar Dashboard tidak error.
            if not data:
                logger.warning(f"[Pipeline] Tidak ada data yang berhasil diambil untuk '{keyword}'")
                # Buat CSV kosong yang valid (header saja) agar /api/download tidak 404
                empty_csv = generate_csv_output([])
                file_path  = DATA_DIR / f"{req_id}.csv"
                with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
                    f.write(empty_csv)
                _update_status(
                    req_id, COMPLETED,
                    f"Tidak ada data yang berhasil diambil untuk '{keyword}'. "
                    "Coba kata kunci lain atau perbarui cookie X (jalankan: python export_twitter_cookies.py).",
                    100,
                    total_results=0,
                    file_path=str(file_path),
                    summary={"Positif": 0, "Negatif": 0, "Netral": 0, "total": 0},
                    keyword=keyword,
                )
                return

            _update_status(req_id, INFERENCING, "Menganalisis sentimen...", 50)

            raw_texts    = [t.get("raw_text", "")  for t in data]
            dates        = [t.get("date",     "")  for t in data]
            sources_list = [t.get("source",   "")  for t in data]
            clean_texts  = [preprocess_text(text)  for text in raw_texts]
            clean_texts  = [t[:1000] for t in clean_texts]  # cap: cegah tokenizer hang pada teks sangat panjang

            ITEM_TIMEOUT_SEC = 30
            def _fallback_pred():
                return {
                    "predicted_label": "Netral",
                    "confidence_positive": 0.333,
                    "confidence_negative": 0.333,
                    "confidence_neutral": 0.334,
                    "inference_time_ms": 0.0,
                }

            predictions = []
            total = len(clean_texts)
            batch_size = 32
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="bert-infer") as infer_pool:
                for i in range(0, total, batch_size):
                    batch_texts = clean_texts[i : i + batch_size]
                    logger.info(f"[Inference] Batch {i//batch_size + 1} | size={len(batch_texts)} | items {i+1}-{i+len(batch_texts)}/{total}")
                    t0 = time.perf_counter()
                    future = infer_pool.submit(predict_batch, batch_texts, batch_size)
                    try:
                        batch_preds = future.result(timeout=ITEM_TIMEOUT_SEC * len(batch_texts))
                    except FuturesTimeoutError:
                        logger.warning(f"[Inference] Batch {i//batch_size + 1} timeout — fallback Netral untuk {len(batch_texts)} item")
                        batch_preds = [_fallback_pred() for _ in batch_texts]
                    except Exception as batch_err:
                        logger.error(f"[Inference] Batch {i//batch_size + 1} gagal: {batch_err}", exc_info=True)
                        batch_preds = [_fallback_pred() for _ in batch_texts]
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    logger.info(f"[Inference] ✓ Batch {i//batch_size + 1} selesai dalam {elapsed_ms:.0f}ms")
                    predictions.extend(batch_preds)
                    processed = min(i + batch_size, total)
                    progress = 50 + int((processed / total) * 45)
                    _update_status(req_id, INFERENCING, f"Menganalisis sentimen... ({processed}/{total})", progress)
                    time.sleep(0.05)  # release GIL so Flask can serve status polls

            _update_status(req_id, FINALIZING, "Menyusun hasil...", 95)
            logger.info(f"[Pipeline] FINALIZING: menyusun {len(predictions)} hasil...")

            results = []
            for raw, clean, date, src, pred in zip(raw_texts, clean_texts, dates, sources_list, predictions):
                results.append({
                    "raw_text":            raw,
                    "clean_text":          clean,
                    "date":                date,
                    "source":              src,
                    "predicted_label":     pred.get("predicted_label",     "Netral"),
                    "confidence_positive": pred.get("confidence_positive", 0.0),
                    "confidence_negative": pred.get("confidence_negative", 0.0),
                    "confidence_neutral":  pred.get("confidence_neutral",  0.0),
                    "inference_time_ms":   pred.get("inference_time_ms",   0.0),
                })

            logger.info(f"[Pipeline] FINALIZING: results siap, generate CSV...")
            _update_status(req_id, FINALIZING, "Menyimpan data...", 97)

            csv_content = generate_csv_output(results)
            logger.info(f"[Pipeline] FINALIZING: CSV {len(csv_content)} chars, menulis ke disk...")
            file_path = DATA_DIR / f"{req_id}.csv"
            with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(csv_content)
            logger.info(f"[Pipeline] FINALIZING: CSV tersimpan → {file_path}")

            _update_status(req_id, FINALIZING, "Menghitung ringkasan...", 99)
            summary = calculate_summary(results)
            logger.info(f"[Pipeline] FINALIZING: ringkasan selesai → {summary}")

            _update_status(req_id, COMPLETED, "Selesai", 100,
                           total_results=len(results),
                           file_path=str(file_path),
                           summary=summary,
                           keyword=keyword)
            logger.info(f"[Pipeline] COMPLETED: {len(results)} item")

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
