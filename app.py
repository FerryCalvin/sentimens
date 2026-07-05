# ============================================================
# app.py — Flask Main Application Server (Port 5000)
# Sistem Klasifikasi Sentimen IndoBERT Multi-Domain
# ============================================================
import json
import logging
import os
import threading

import pandas as pd
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
)
from markupsafe import escape

from config import (
    SECRET_KEY,
    MAX_CONTENT_LENGTH,
    DEBUG,
    DEFAULT_SCRAPE_LIMIT,
    DEFAULT_DAYS_BACK,
)
from preprocessing import preprocess_text
from inference import load_model, predict_sentiment, predict_batch
import job_store
from utils import (
    sanitize_input,
    validate_csv,
    detect_text_column,
    generate_csv_output,
    calculate_summary,
    format_confidence,
    get_confidence_badge_class,
)

# ---- Konfigurasi Logging ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---- Inisialisasi Flask ----
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# ---- Template Filters ----
app.jinja_env.filters["format_confidence"] = format_confidence
app.jinja_env.filters["badge_class"] = get_confidence_badge_class


# ---- FR-AI-01: Muat model saat startup ----
logger.info("Memuat model IndoBERT...")
try:
    _model, _tokenizer = load_model()
    logger.info("Model berhasil dimuat dan siap menerima permintaan.")
    MODEL_LOADED = True
except Exception as e:
    logger.error(f"GAGAL memuat model: {e}")
    MODEL_LOADED = False


# =============================================================
# ROUTE: Halaman Utama — Analisis Teks Tunggal (EP-01)
# =============================================================

@app.route("/", methods=["GET"])
def index():
    """Halaman utama dengan form analisis teks tunggal."""
    return render_template(
        "index.html",
        model_loaded=MODEL_LOADED,
        default_limit=DEFAULT_SCRAPE_LIMIT,
        default_days_back=DEFAULT_DAYS_BACK,
    )


# =============================================================
# API ENDPOINT: Health Check
# =============================================================

@app.route("/api/health")
def health_check():
    """Endpoint untuk mengecek status server dan model."""
    return jsonify({
        "status": "ok",
        "model_loaded": MODEL_LOADED,
        "service": "Flask Sentiment Analysis",
        "port": 5000,
    })


# =============================================================
# API JSON ENDPOINTS — dipanggil oleh UI via fetch()
# (Semua route lama tetap ada, ini hanya tambahan baru)
# =============================================================

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """JSON endpoint analisis teks tunggal — dipanggil SPA via fetch()."""
    if not MODEL_LOADED:
        return jsonify({"error": "Model belum dimuat."}), 503

    body     = request.get_json(force=True, silent=True) or {}
    raw_text = str(body.get("text", "")).strip()

    if not raw_text or len(raw_text) < 3:
        return jsonify({"error": "Teks terlalu pendek (minimal 3 karakter)."}), 400

    raw_text = str(escape(raw_text))

    try:
        clean_text = preprocess_text(raw_text)[:1000]
        result     = predict_sentiment(clean_text)
        return jsonify({
            "raw_text":            raw_text,
            "clean_text":          clean_text,
            "predicted_label":     result["predicted_label"],
            "confidence_positive": result["confidence_positive"],
            "confidence_negative": result["confidence_negative"],
            "confidence_neutral":  result["confidence_neutral"],
            "inference_time_ms":   result["inference_time_ms"],
        })
    except Exception as e:
        logger.error(f"/api/analyze error: {e}", exc_info=True)
        return jsonify({"error": "Terjadi kesalahan saat menganalisis."}), 500


def _load_batch_results_payload(req_id: str) -> dict | None:
    """Baca hasil batch dari CSV. Dipakai bersama oleh POST /api/batch dan GET /api/batch/results/<req_id>."""
    from pipeline import DATA_DIR
    from utils import load_results_from_csv

    file_path = DATA_DIR / f"{req_id}.csv"
    if not file_path.exists():
        return None

    results = load_results_from_csv(str(file_path))
    try:
        with open(file_path, encoding="utf-8-sig") as f:
            csv_content = f.read()
    except Exception:
        csv_content = generate_csv_output(results)

    return {
        "req_id":        req_id,
        "results":       results[:100],
        "total_results": len(results),
        "summary":       calculate_summary(results),
        "csv_content":   csv_content,
    }


def _run_batch_job(job_id: str, raw_texts: list) -> None:
    """Dijalankan di background thread — update job_store di tiap tahap."""
    from pipeline import run_batch_pipeline

    def progress_cb(stage, percent, message=""):
        job_store.update_job(job_id, status="running", stage=stage, percent=percent, message=message)

    try:
        pipeline_result = run_batch_pipeline(raw_texts, req_id=job_id, progress_cb=progress_cb)
        payload = _load_batch_results_payload(pipeline_result["req_id"])
        job_store.update_job(job_id, status="done", stage="done", percent=100, message="Selesai", result=payload)
    except Exception as e:
        logger.error(f"/api/batch job error: {e}", exc_info=True)
        job_store.update_job(job_id, status="error", error="Terjadi kesalahan saat memproses CSV.")


@app.route("/api/batch", methods=["POST"])
def api_batch():
    """JSON endpoint batch CSV — memproses di background thread, kembalikan job_id untuk polling."""
    if not MODEL_LOADED:
        return jsonify({"error": "Model belum dimuat."}), 503

    csv_file = request.files.get("csv_file")
    is_valid, error_msg, df = validate_csv(csv_file)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    text_col = detect_text_column(df)
    if text_col is None:
        return jsonify({"error": "Tidak dapat mendeteksi kolom teks."}), 400

    raw_texts = df[text_col].fillna("").tolist()
    job_id = job_store.create_job()
    threading.Thread(target=_run_batch_job, args=(job_id, raw_texts), daemon=True).start()
    return jsonify({"job_id": job_id, "status": "queued"}), 202


@app.route("/api/batch/status/<job_id>", methods=["GET"])
def api_batch_status(job_id):
    job = job_store.get_job(sanitize_input(str(job_id)))
    if job is None:
        return jsonify({"error": "Job not found."}), 404
    return jsonify(job)


@app.route("/api/batch/results/<req_id>", methods=["GET"])
def api_batch_results(req_id):
    """Return hasil batch tersimpan untuk reload/download."""
    req_id_clean = sanitize_input(str(req_id))
    payload = _load_batch_results_payload(req_id_clean)
    if payload is None:
        return jsonify({"error": "Results not ready or not found."}), 404
    return jsonify(payload)


def _build_results_payload(req_id: str, days: int | None = None) -> dict:
    """Agregasi hasil scrape/batch dari CSV untuk dashboard. Dipakai bersama oleh
    POST /api/scrape dan GET /api/results/<req_id>."""
    from utils import get_overall_distribution, get_timeline_data, get_top_items, filter_df_by_days, get_word_freq_for_df, load_dataframe_cached, compute_confidence_avg
    from config import MODEL_METRICS

    df = load_dataframe_cached(req_id)
    df_filtered = filter_df_by_days(df, days) if days is not None else df

    # top_items and confidence_avg use original Indonesian column names
    top_items_raw = get_top_items(df, n=100)
    top_items = []
    for item in top_items_raw:
        top_items.append({
            "raw_text":            item.get("teks_asli", ""),
            "source":              item.get("source", ""),
            "date":                str(item.get("date", "")),
            "predicted_label":     item.get("sentimen", ""),
            "confidence_positive": float(item.get("confidence_positif", 0)),
            "confidence_negative": float(item.get("confidence_negatif", 0)),
            "confidence_neutral":  float(item.get("confidence_netral", 0)),
            "confidence_overall":  float(item.get("confidence", 0)),
        })

    confidence_avg = compute_confidence_avg(df)

    # timeline, distribution, and word_freq respect the active date filter
    dist = get_overall_distribution(df_filtered)
    return {
        "req_id": req_id,
        "distribution": dist,
        "summary": {
            "total":          dist["total"],
            "positive_count": dist["positive"],
            "neutral_count":  dist["neutral"],
            "negative_count": dist["negative"],
        },
        "timeline":       get_timeline_data(df_filtered),
        "word_freq":      get_word_freq_for_df(df_filtered),
        "confidence_avg": confidence_avg,
        "top_items":      top_items,
        "model_metrics":  MODEL_METRICS,
        "total_results":  len(df),
    }


def _run_scrape_job(job_id: str, keyword: str, limit: int, sources: list, mode: str, days_back: int) -> None:
    """Dijalankan di background thread — update job_store di tiap tahap."""
    from pipeline import run_scrape_pipeline

    def progress_cb(stage, percent, message=""):
        job_store.update_job(job_id, status="running", stage=stage, percent=percent, message=message)

    try:
        pipeline_result = run_scrape_pipeline(
            keyword, limit, sources, mode=mode, days_back=days_back,
            req_id=job_id, progress_cb=progress_cb,
        )
        payload = _build_results_payload(pipeline_result["req_id"])
        payload["keyword"] = pipeline_result["keyword"]
        job_store.update_job(job_id, status="done", stage="done", percent=100, message="Selesai", result=payload)
    except Exception as e:
        logger.error(f"/api/scrape pipeline error: {e}", exc_info=True)
        job_store.update_job(job_id, status="error", error="Terjadi kesalahan saat memulai scraping.")


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    """JSON endpoint live scraping — memproses di background thread, kembalikan job_id untuk polling."""
    if not MODEL_LOADED:
        return jsonify({"error": "Model belum dimuat."}), 503

    body    = request.get_json(force=True, silent=True) or {}
    keyword = str(body.get("keyword", "")).strip()
    if not keyword:
        return jsonify({"error": "Kata kunci tidak boleh kosong."}), 400

    keyword = str(escape(keyword))
    try:
        limit = int(body.get("limit", DEFAULT_SCRAPE_LIMIT))
        limit = max(10, min(limit, 500))
    except (ValueError, TypeError):
        limit = DEFAULT_SCRAPE_LIMIT

    sources = ["twitter", "web", "threads"]  # selalu scrape semua sumber
    mode = body.get("mode", "live")
    try:
        days_back = int(body.get("days_back", DEFAULT_DAYS_BACK))
        days_back = max(1, min(days_back, 30))
    except (ValueError, TypeError):
        days_back = DEFAULT_DAYS_BACK

    job_id = job_store.create_job()
    threading.Thread(
        target=_run_scrape_job, args=(job_id, keyword, limit, sources, mode, days_back), daemon=True
    ).start()
    return jsonify({"job_id": job_id, "status": "queued"}), 202


@app.route("/api/scrape/status/<job_id>", methods=["GET"])
def api_scrape_status(job_id):
    job = job_store.get_job(sanitize_input(str(job_id)))
    if job is None:
        return jsonify({"error": "Job not found."}), 404
    return jsonify(job)


# =============================================================
@app.route("/api/results/precomputed", methods=["GET"])
def api_precomputed():
    from utils import get_overall_distribution, get_timeline_data, get_top_items, load_dataframe_cached
    if not os.path.exists(os.path.join("data", "precomputed_large.csv")):
        return jsonify({"error": "Pre-computed data not found."}), 404
    df = load_dataframe_cached("precomputed")
    from config import MODEL_METRICS
    return jsonify({
        "distribution": get_overall_distribution(df),
        "timeline": get_timeline_data(df),
        "top_items": get_top_items(df, n=100),
        "model_metrics": MODEL_METRICS
    })

@app.route("/api/results/<req_id>", methods=["GET"])
def api_results(req_id):
    from pipeline import DATA_DIR

    req_id_clean = sanitize_input(str(req_id))
    file_path = DATA_DIR / f"{req_id_clean}.csv"
    if not file_path.exists():
        return jsonify({"error": "Results not ready or not found."}), 404

    days_param = request.args.get('days')
    days = int(days_param) if days_param and days_param.isdigit() else None

    try:
        return jsonify(_build_results_payload(req_id_clean, days))
    except Exception as e:
        logger.error(f"Failed to read CSV for {req_id_clean}: {e}")
        return jsonify({"error": "Gagal membaca file hasil."}), 500


@app.route("/api/export/<req_id>", methods=["GET"])
def api_export(req_id):
    """Ekspor hasil analisis (scrape atau batch) sebagai laporan Excel atau PDF."""
    from pipeline import DATA_DIR
    from utils import load_dataframe_cached, compute_confidence_avg, get_overall_distribution
    from export_report import generate_excel_report, generate_pdf_report

    fmt = request.args.get("format", "xlsx").lower()
    if fmt not in ("xlsx", "pdf"):
        return jsonify({"error": "Format tidak didukung. Gunakan xlsx atau pdf."}), 400

    req_id_clean = sanitize_input(str(req_id))
    file_path = DATA_DIR / f"{req_id_clean}.csv"
    if not file_path.exists():
        return jsonify({"error": "Data tidak ditemukan."}), 404

    df = load_dataframe_cached(req_id_clean)
    dist = get_overall_distribution(df)
    total = dist["total"]
    summary = {
        "total":       total,
        "positif":     dist["positive"],
        "negatif":     dist["negative"],
        "netral":      dist["neutral"],
        "positif_pct": round(dist["positive"] / total * 100, 1) if total else 0.0,
        "negatif_pct": round(dist["negative"] / total * 100, 1) if total else 0.0,
        "netral_pct":  round(dist["neutral"]  / total * 100, 1) if total else 0.0,
    }
    confidence_avg = compute_confidence_avg(df)

    if fmt == "xlsx":
        buf = generate_excel_report(df, summary, confidence_avg)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"laporan_{req_id_clean}.xlsx",
        )

    buf = generate_pdf_report(df, summary, confidence_avg, keyword=request.args.get("keyword", ""))
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"laporan_{req_id_clean}.pdf",
    )


@app.route("/api/evaluate", methods=["POST"])
def api_evaluate():
    import pandas as pd
    from inference import predict_batch
    from utils import compute_evaluation_metrics

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "File tidak ditemukan."}), 400

    try:
        df = pd.read_csv(file)
    except Exception:
        return jsonify({"error": "File CSV tidak valid."}), 400

    if "teks_asli" not in df.columns or "label_asli" not in df.columns:
        return jsonify({"error": "CSV harus memiliki kolom 'teks_asli' dan 'label_asli'."}), 400

    df = df.dropna(subset=["teks_asli", "label_asli"])
    valid_labels = {"Positif", "Negatif", "Netral"}
    df = df[df["label_asli"].isin(valid_labels)]
    if df.empty:
        return jsonify({"error": "Tidak ada baris valid setelah filtering label."}), 400

    texts = [t[:1000] for t in df["teks_asli"].astype(str).tolist()]
    true_labels = df["label_asli"].astype(str).tolist()

    predictions = predict_batch(texts)
    pred_labels = [p["predicted_label"] for p in predictions]

    return jsonify(compute_evaluation_metrics(true_labels, pred_labels))


# Error Handlers (NFR-S-05)
# =============================================================

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Berkas terlalu besar. Maksimum 16 MB."}), 413


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", 
                          error_code=404,
                          error_message="Halaman tidak ditemukan."), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {e}")
    return render_template("error.html",
                          error_code=500,
                          error_message="Terjadi kesalahan internal server."), 500


# =============================================================
# Entry Point
# =============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=DEBUG,
        use_reloader=False,  # Disable reloader agar model tidak dimuat dua kali
        threaded=True,       # Wajib: route scrape/batch sekarang blocking (bisa puluhan detik)
    )
