import uuid
import httpx
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

from config import SCRAPER_BASE_URL, SCRAPER_ENDPOINT, SCRAPER_TIMEOUT
from inference import predict_batch
from preprocessing import preprocess_text
from utils import generate_csv_output, calculate_summary

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


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


def _scrape_in_process(keyword: str, limit: int, sources: list) -> list:
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

        if need_web:
            results.extend(web_data)
            logger.info(f"[Pipeline] Web: {len(web_data)} hasil")

    # Deduplicate
    seen = set()
    unique = []
    for item in results:
        t = item.get("raw_text", "")[:80]
        if t and t not in seen:
            seen.add(t)
            unique.append(item)

    return unique[:limit]


def _fallback_pred() -> dict:
    return {
        "predicted_label": "Netral",
        "confidence_positive": 0.333,
        "confidence_negative": 0.333,
        "confidence_neutral": 0.334,
        "inference_time_ms": 0.0,
    }


def _predict_all(clean_texts: list[str]) -> list[dict]:
    """Jalankan inferensi batch dengan satu timeout keseluruhan sebagai jaring pengaman."""
    if not clean_texts:
        return []
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="bert-infer") as pool:
        future = pool.submit(predict_batch, clean_texts)
        try:
            return future.result(timeout=30 * len(clean_texts))
        except FuturesTimeoutError:
            logger.warning(f"[Inference] Timeout — fallback Netral untuk {len(clean_texts)} item")
            return [_fallback_pred() for _ in clean_texts]
        except Exception as e:
            logger.error(f"[Inference] Gagal: {e}", exc_info=True)
            return [_fallback_pred() for _ in clean_texts]


def run_scrape_pipeline(keyword: str, limit: int, sources: list[str], mode: str = "live", days_back: int = 7) -> dict:
    req_id = str(uuid.uuid4())

    try:
        scraper_url = f"{SCRAPER_BASE_URL}{SCRAPER_ENDPOINT}"
        response = httpx.post(
            scraper_url,
            json={"keyword": keyword, "limit": limit, "sources": sources, "days_back": days_back},
            timeout=httpx.Timeout(
                connect=10.0,   # Koneksi awal cepat (scraper harus sudah jalan)
                read=300.0,     # Tunggu 5 menit untuk scraping selesai
                write=10.0,
                pool=5.0,
            ),
        )
        response.raise_for_status()
        scraper_data = response.json()
        if scraper_data.get("status") == "success":
            data = scraper_data.get("data", [])
            logger.info(f"[Pipeline] Scraper eksternal: {len(data)} hasil")
        else:
            data = []
    except Exception as ext_err:
        logger.warning(f"[Pipeline] Scraper eksternal tidak tersedia ({ext_err}), pakai in-process scraping")
        data = _scrape_in_process(keyword, limit, sources)

    # Graceful handling jika 0 hasil — buat CSV kosong agar dashboard tidak error.
    if not data:
        logger.warning(f"[Pipeline] Tidak ada data yang berhasil diambil untuk '{keyword}'")
        empty_csv = generate_csv_output([])
        file_path = DATA_DIR / f"{req_id}.csv"
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(empty_csv)
        return {
            "req_id": req_id,
            "total_results": 0,
            "file_path": str(file_path),
            "summary": {"Positif": 0, "Negatif": 0, "Netral": 0, "total": 0},
            "keyword": keyword,
        }

    raw_texts    = [t.get("raw_text", "") for t in data]
    dates        = [t.get("date",     "") for t in data]
    sources_list = [t.get("source",   "") for t in data]
    clean_texts  = [preprocess_text(text)[:1000] for text in raw_texts]  # cap: cegah tokenizer hang

    logger.info(f"[Pipeline] Menganalisis sentimen untuk {len(clean_texts)} item...")
    t0 = time.perf_counter()
    predictions = _predict_all(clean_texts)
    logger.info(f"[Pipeline] Inferensi selesai dalam {(time.perf_counter() - t0) * 1000:.0f}ms")

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

    csv_content = generate_csv_output(results)
    file_path = DATA_DIR / f"{req_id}.csv"
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(csv_content)
    logger.info(f"[Pipeline] CSV tersimpan → {file_path}")

    summary = calculate_summary(results)
    logger.info(f"[Pipeline] Selesai: {len(results)} item")

    return {
        "req_id": req_id,
        "total_results": len(results),
        "file_path": str(file_path),
        "summary": summary,
        "keyword": keyword,
    }


def run_batch_pipeline(raw_texts: list[str]) -> dict:
    req_id = str(uuid.uuid4())

    clean_texts = [
        preprocess_text(str(text).strip())[:1000] if str(text).strip() else ""
        for text in raw_texts
    ]

    logger.info(f"[Batch] Menganalisis sentimen untuk {len(clean_texts)} baris...")
    predictions = _predict_all(clean_texts)

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

    return {
        "req_id": req_id,
        "total_results": len(results),
        "file_path": str(file_path),
        "summary": summary,
    }
