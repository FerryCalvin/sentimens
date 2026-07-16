import uuid
import httpx
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from pathlib import Path

from config import (
    SCRAPER_BASE_URL, SCRAPER_ENDPOINT, SCRAPER_TIMEOUT,
    INFERENCE_TIMEOUT_PER_ITEM_SEC, INFERENCE_TIMEOUT_MIN_SEC, INFERENCE_TIMEOUT_MAX_SEC,
)
from inference import predict_batch
from preprocessing import preprocess_text, is_valid_text
from utils import generate_csv_output, calculate_summary, remove_outliers_and_duplicates, filter_news_style_content

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def _scrape_via_subprocess(keyword: str, limit: int, source_type: str) -> list:
    """
    Jalankan scraper_worker.py sebagai subprocess terpisah untuk satu source.
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
            [python, worker, keyword, str(limit), source_type],
            capture_output=True,
            text=True,
            encoding="utf-8",    # FIX #2: paksa UTF-8, bukan cp1252
            errors="replace",    # FIX #2: karakter invalid diganti '?', tidak crash
            timeout=300,         # FIX #1: diperpanjang dari 90s → 300s
            cwd=os.path.dirname(__file__),
            env=env,
        )
        if result.returncode != 0:
            logger.warning(f"[Worker:{source_type}] stderr: {result.stderr[:400]}")

        stdout = result.stdout.strip() if result.stdout else ""
        if stdout:
            data = _json.loads(stdout)
            for item in data:
                item["source"] = source_type
            return data
        return []
    except subprocess.TimeoutExpired:
        logger.error(f"[Worker:{source_type}] Subprocess timeout (300s)")
        return []
    except Exception as e:
        logger.error(f"[Worker:{source_type}] Subprocess error: {e}")
        return []


def _scrape_in_process(keyword: str, limit: int, sources: list, progress_cb=None) -> list:
    """
    Scrape semua source yang diminta secara paralel, masing-masing lewat
    subprocess worker terpisah (fallback saat scraper service eksternal mati).
    """
    need_sources = []
    if "twitter" in sources:
        need_sources.append("twitter")
    if "web" in sources or "news" in sources:
        need_sources.append("web")
    if "threads" in sources:
        need_sources.append("threads")

    results = []
    if need_sources:
        limit_per_source = max(5, limit // len(need_sources))
        logger.info(f"[Pipeline] Fallback in-process scraping: {keyword} | sources={need_sources}")

        done_count = 0
        with ThreadPoolExecutor(max_workers=len(need_sources), thread_name_prefix="scrape-fallback") as pool:
            futures = {
                pool.submit(_scrape_via_subprocess, keyword, limit_per_source, src): src
                for src in need_sources
            }
            for future in as_completed(futures):
                src = futures[future]
                try:
                    data = future.result()
                except Exception as e:
                    logger.error(f"[Pipeline] Fallback {src} gagal: {e}")
                    data = []
                results.extend(data)
                done_count += 1
                logger.info(f"[Pipeline] Fallback {src}: {len(data)} hasil")
                if progress_cb:
                    progress_cb(done_count, len(need_sources))

    return results


def _fallback_pred() -> dict:
    return {
        "predicted_label": "Netral",
        "confidence_positive": 0.333,
        "confidence_negative": 0.333,
        "confidence_neutral": 0.334,
        "inference_time_ms": 0.0,
    }


def _skipped_pred() -> dict:
    return {
        "predicted_label": "Netral",
        "confidence_positive": 0.0,
        "confidence_negative": 0.0,
        "confidence_neutral": 0.0,
        "inference_time_ms": 0.0,
        "skipped": True,
        "skip_reason": "Dilewati: konten tidak cukup setelah pembersihan",
    }


def _noop_progress(stage: str, percent: int, message: str = "") -> None:
    pass


def _inference_timeout(n_items: int) -> float:
    return min(INFERENCE_TIMEOUT_MAX_SEC, max(INFERENCE_TIMEOUT_MIN_SEC, INFERENCE_TIMEOUT_PER_ITEM_SEC * n_items))


def _predict_all(clean_texts: list[str], progress_cb=None) -> list[dict]:
    """Jalankan inferensi batch dengan satu timeout keseluruhan sebagai jaring pengaman.

    Tidak memakai `with ThreadPoolExecutor(...)`: keluar dari context manager memanggil
    `shutdown(wait=True)`, yang akan tetap memblokir caller sampai worker yang sudah
    dianggap timeout benar-benar selesai — meniadakan timeout itu sendiri. `shutdown(wait=False)`
    dipanggil eksplisit di tiap cabang supaya caller benar-benar terbebas begitu timeout tercapai.
    """
    if not clean_texts:
        return []
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bert-infer")
    future = pool.submit(predict_batch, clean_texts, 32, progress_cb)
    timeout = _inference_timeout(len(clean_texts))
    try:
        result = future.result(timeout=timeout)
        pool.shutdown(wait=False)
        return result
    except FuturesTimeoutError:
        logger.warning(
            f"[Inference] Timeout setelah {timeout:.0f}s — fallback Netral untuk {len(clean_texts)} item "
            "(worker thread dibiarkan jalan di background, hasilnya dibuang)."
        )
        pool.shutdown(wait=False)
        return [_fallback_pred() for _ in clean_texts]
    except Exception as e:
        logger.error(f"[Inference] Gagal: {e}", exc_info=True)
        pool.shutdown(wait=False)
        return [_fallback_pred() for _ in clean_texts]


def _predict_valid_only(clean_texts: list[str], progress_cb=None) -> list[dict]:
    """Hanya kirim teks yang lolos is_valid_text() (min_chars=3) ke model;
    sisanya ditandai skip tanpa memanggil model sama sekali."""
    valid_idx = [i for i, t in enumerate(clean_texts) if is_valid_text(t)]
    valid_preds = _predict_all([clean_texts[i] for i in valid_idx], progress_cb=progress_cb)
    predictions = [_skipped_pred() for _ in clean_texts]
    for idx, pred in zip(valid_idx, valid_preds):
        predictions[idx] = pred
    return predictions


def run_scrape_pipeline(
    keyword: str,
    limit: int,
    sources: list[str],
    mode: str = "live",
    days_back: int = 7,
    req_id: str | None = None,
    progress_cb=None,
) -> dict:
    req_id = req_id or str(uuid.uuid4())
    progress_cb = progress_cb or _noop_progress

    progress_cb("scraping", 5, "Mengambil data dari Twitter/X, Web, dan Threads...")

    expanded_keyword = keyword
    plain_keyword = keyword
    expansion_status = "scraper_service_unavailable_fallback"

    try:
        scraper_url = f"{SCRAPER_BASE_URL}{SCRAPER_ENDPOINT}"
        response = httpx.post(
            scraper_url,
            json={"keyword": keyword, "limit": limit, "sources": sources, "days_back": days_back},
            timeout=httpx.Timeout(
                connect=10.0,           # Koneksi awal cepat (scraper harus sudah jalan)
                read=SCRAPER_TIMEOUT,   # Harus >= timeout internal scraper service
                write=10.0,
                pool=5.0,
            ),
        )
        response.raise_for_status()
        scraper_data = response.json()
        if scraper_data.get("status") == "success":
            data = scraper_data.get("data", [])
            expanded_keyword = scraper_data.get("expanded_keyword", keyword)
            plain_keyword = scraper_data.get("plain_keyword", keyword)
            expansion_status = scraper_data.get("expansion_status", "unknown")
            logger.info(f"[Pipeline] Scraper eksternal: {len(data)} hasil")
        else:
            data = []
    except Exception as ext_err:
        logger.warning(f"[Pipeline] Scraper eksternal tidak tersedia ({ext_err}), pakai in-process scraping")

        def _scrape_sub_cb(done: int, total: int) -> None:
            pct = 5 + int(45 * done / total) if total else 50
            progress_cb("scraping", pct, f"Scraping fallback: {done}/{total} sumber selesai")

        data = _scrape_in_process(keyword, limit, sources, progress_cb=_scrape_sub_cb)

    progress_cb("scraping", 50, "Scraping selesai.")

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
            "expanded_keyword": expanded_keyword,
            "plain_keyword": plain_keyword,
            "expansion_status": expansion_status,
        }

    data, outlier_stats = remove_outliers_and_duplicates(data, text_key="raw_text")

    data, news_stats = filter_news_style_content(data)
    outlier_stats["news_account_removed"] = news_stats["news_account_removed"]
    outlier_stats["news_style_removed"] = news_stats["news_style_removed"]
    outlier_stats["total_after"] = news_stats["total_after"]

    data = data[:limit]
    logger.info(
        f"[Pipeline] Filter data mentah: {outlier_stats['total_before']} -> {outlier_stats['total_after']} "
        f"(duplikat={outlier_stats['duplicates_removed']}, kosong={outlier_stats['empty_removed']}, "
        f"outlier={outlier_stats['outliers_removed']}, akun_berita={outlier_stats['news_account_removed']}, "
        f"gaya_berita={outlier_stats['news_style_removed']})"
    )
    progress_cb(
        "filtering", 52,
        f"Menyaring {outlier_stats['duplicates_removed']} duplikat, "
        f"{outlier_stats['outliers_removed']} outlier, dan "
        f"{outlier_stats['news_account_removed'] + outlier_stats['news_style_removed']} konten berita...",
    )

    if not data:
        logger.warning(f"[Pipeline] Seluruh data untuk '{keyword}' tersaring sebagai duplikat/outlier")
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
            "expanded_keyword": expanded_keyword,
            "plain_keyword": plain_keyword,
            "expansion_status": expansion_status,
            "outlier_stats": outlier_stats,
        }

    raw_texts    = [t.get("raw_text", "") for t in data]
    dates        = [t.get("date",     "") for t in data]
    sources_list = [t.get("source",   "") for t in data]

    progress_cb("preprocessing", 55, "Praproses teks...")
    clean_texts  = [preprocess_text(text)[:1000] for text in raw_texts]  # cap: cegah tokenizer hang
    progress_cb("preprocessing", 60, "Praproses selesai.")

    for i, (raw, clean) in enumerate(zip(raw_texts[:5], clean_texts[:5])):
        logger.info(f"[Pipeline][Sample {i+1}] raw={raw[:80]!r} -> clean={clean[:80]!r}")

    def _infer_cb(done: int, total: int) -> None:
        pct = 60 + int(40 * done / total) if total else 100
        progress_cb("predicting", pct, f"Menganalisis sentimen ({done}/{total})...")

    logger.info(f"[Pipeline] Menganalisis sentimen untuk {len(clean_texts)} item...")
    t0 = time.perf_counter()
    predictions = _predict_valid_only(clean_texts, progress_cb=_infer_cb)
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
            "skipped":             pred.get("skipped", False),
            "skip_reason":         pred.get("skip_reason", ""),
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
        "expanded_keyword": expanded_keyword,
        "plain_keyword": plain_keyword,
        "expansion_status": expansion_status,
        "outlier_stats": outlier_stats,
    }


def run_batch_pipeline(raw_texts: list[str], req_id: str | None = None, progress_cb=None) -> dict:
    req_id = req_id or str(uuid.uuid4())
    progress_cb = progress_cb or _noop_progress

    progress_cb("preprocessing", 2, "Praproses data...")
    clean_texts = [
        preprocess_text(str(text).strip())[:1000] if str(text).strip() else ""
        for text in raw_texts
    ]
    progress_cb("preprocessing", 10, "Praproses selesai.")

    for i, (raw, clean) in enumerate(zip(raw_texts[:5], clean_texts[:5])):
        logger.info(f"[Batch][Sample {i+1}] raw={str(raw)[:80]!r} -> clean={clean[:80]!r}")

    def _infer_cb(done: int, total: int) -> None:
        pct = 10 + int(90 * done / total) if total else 100
        progress_cb("predicting", pct, f"Menganalisis sentimen ({done}/{total})...")

    logger.info(f"[Batch] Menganalisis sentimen untuk {len(clean_texts)} baris...")
    predictions = _predict_valid_only(clean_texts, progress_cb=_infer_cb)

    results = []
    for raw, clean, pred in zip(raw_texts, clean_texts, predictions):
        raw_str = str(raw).strip()
        results.append({
            "raw_text": raw_str,
            "clean_text": clean,
            "predicted_label": pred.get("predicted_label", "Netral"),
            "confidence_positive": pred.get("confidence_positive", 0.0),
            "confidence_negative": pred.get("confidence_negative", 0.0),
            "confidence_neutral": pred.get("confidence_neutral", 0.0),
            "inference_time_ms": pred.get("inference_time_ms", 0.0),
            "skipped": pred.get("skipped", False),
            "skip_reason": pred.get("skip_reason", ""),
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
