# ============================================================
# app.py — Flask Main Application Server (Port 5000)
# Sistem Klasifikasi Sentimen IndoBERT Multi-Domain
# ============================================================
import io
import json
import logging
import os

import httpx
import pandas as pd
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
    session,
)
from markupsafe import escape

from config import (
    SECRET_KEY,
    MAX_CONTENT_LENGTH,
    DEBUG,
    SCRAPER_BASE_URL,
    SCRAPER_ENDPOINT,
    SCRAPER_TIMEOUT,
    DEFAULT_SCRAPE_LIMIT,
    DEFAULT_DAYS_BACK,
    LABEL_COLORS,
)
from preprocessing import preprocess_text, get_word_frequencies, is_valid_text
from inference import load_model, predict_sentiment, predict_batch
from utils import (
    sanitize_input,
    validate_csv,
    detect_text_column,
    generate_csv_output,
    calculate_summary,
    prepare_chart_data,
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


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    FR-ST-01, FR-ST-02, FR-ST-03: Endpoint analisis teks tunggal.
    Alur: Input → Praproses → Tokenisasi → Inferensi → Render Hasil
    """
    if not MODEL_LOADED:
        flash("Model AI belum berhasil dimuat. Silakan periksa konfigurasi server.", "danger")
        return redirect(url_for("index"))
    
    # US-01.4: Validasi input
    raw_text = request.form.get("text", "").strip()
    if not raw_text:
        flash("Teks tidak boleh kosong. Silakan masukkan teks untuk dianalisis.", "warning")
        return redirect(url_for("index"))
    
    # NFR-S-02: Sanitasi input
    raw_text = str(escape(raw_text))
    
    # US-01.4: Validasi panjang teks minimum
    if len(raw_text) < 3:
        flash("Teks terlalu pendek. Masukkan minimal 3 karakter.", "warning")
        return redirect(url_for("index"))
    
    try:
        # FR-ST-02: Jalankan pipeline pemrosesan
        clean_text = preprocess_text(raw_text)
        result = predict_sentiment(clean_text)
        
        # FR-ST-03: Siapkan data untuk ditampilkan
        context = {
            "raw_text": raw_text,
            "clean_text": clean_text,
            "predicted_label": result["predicted_label"],
            "confidence_positive": result["confidence_positive"],
            "confidence_negative": result["confidence_negative"],
            "confidence_neutral": result["confidence_neutral"],
            "inference_time_ms": result["inference_time_ms"],
            "label_colors": LABEL_COLORS,
            "model_loaded": MODEL_LOADED,
        }
        
        return render_template("result_single.html", **context)
        
    except Exception as e:
        # NFR-S-05: Jangan tampilkan stack trace ke pengguna
        logger.error(f"Error saat analisis teks tunggal: {e}", exc_info=True)
        flash("Terjadi kesalahan saat menganalisis teks. Silakan coba lagi.", "danger")
        return redirect(url_for("index"))


# =============================================================
# ROUTE: Analisis Batch CSV (EP-02)
# =============================================================

@app.route("/batch", methods=["GET"])
def batch():
    """Halaman upload CSV untuk analisis batch."""
    return render_template("batch.html", model_loaded=MODEL_LOADED)


@app.route("/batch", methods=["POST"])
def batch_process():
    """
    FR-BT-01 s/d FR-BT-06: Proses analisis batch dari file CSV.
    """
    if not MODEL_LOADED:
        flash("Model AI belum berhasil dimuat.", "danger")
        return redirect(url_for("batch"))
    
    # FR-BT-01: Dapatkan file dari form
    csv_file = request.files.get("csv_file")
    
    # FR-BT-02: Validasi file
    is_valid, error_msg, df = validate_csv(csv_file)
    if not is_valid:
        flash(error_msg, "warning")
        return redirect(url_for("batch"))
    
    # Deteksi kolom teks
    text_col = detect_text_column(df)
    if text_col is None:
        flash("Tidak dapat mendeteksi kolom teks dalam berkas CSV.", "warning")
        return redirect(url_for("batch"))
    
    try:
        # FR-BT-03 & FR-BT-04: Proses setiap baris
        raw_texts = df[text_col].fillna("").tolist()
        
        # Praproses semua teks
        clean_texts = []
        for text in raw_texts:
            text_str = str(text).strip()
            clean_texts.append(preprocess_text(text_str) if text_str else "")
        
        # Inferensi batch
        predictions = predict_batch(clean_texts)
        
        # Gabungkan hasil
        results = []
        for i, (raw, clean, pred) in enumerate(zip(raw_texts, clean_texts, predictions)):
            raw_str = str(raw).strip()
            
            # FR-BT-04: Skip baris kosong
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
        
        # FR-BT-06: Hitung ringkasan statistik
        summary = calculate_summary(results)
        
        # Siapkan data chart
        chart_data = prepare_chart_data(results)
        
        # Siapkan word frequencies untuk word cloud
        valid_clean_texts = [r["clean_text"] for r in results if r["clean_text"]]
        word_freq = get_word_frequencies(valid_clean_texts)
        
        # Simpan hasil di session untuk download
        # Karena data bisa besar, simpan sebagai CSV string terkompresi
        csv_output = generate_csv_output(results)
        session["batch_csv"] = csv_output
        session["batch_filename"] = (
            csv_file.filename.replace(".csv", "_hasil_sentimen.csv")
            if csv_file.filename
            else "hasil_sentimen.csv"
        )
        
        context = {
            "results": results[:100],  # Tampilkan max 100 baris di tabel
            "total_results": len(results),
            "summary": summary,
            "chart_data": json.dumps(chart_data),
            "word_freq": json.dumps(word_freq),
            "text_column": text_col,
            "model_loaded": MODEL_LOADED,
            "label_colors": LABEL_COLORS,
        }
        
        return render_template("result_batch.html", **context)
        
    except Exception as e:
        logger.error(f"Error saat batch processing: {e}", exc_info=True)
        flash("Terjadi kesalahan saat memproses berkas CSV. Pastikan format CSV valid.", "danger")
        return redirect(url_for("batch"))


@app.route("/download")
def download():
    """
    US-02.3: Download hasil batch dalam format CSV.
    """
    csv_content = session.get("batch_csv")
    filename = session.get("batch_filename", "hasil_sentimen.csv")
    
    if not csv_content:
        flash("Tidak ada hasil yang dapat diunduh. Silakan proses berkas CSV terlebih dahulu.", "warning")
        return redirect(url_for("batch"))
    
    # Buat BytesIO dari string CSV
    output = io.BytesIO(csv_content.encode("utf-8-sig"))  # BOM untuk Excel compatibility
    output.seek(0)
    
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


# =============================================================
# ROUTE: Live Scraping (EP-03)
# =============================================================

@app.route("/scrape", methods=["GET"])
def scrape():
    """Halaman form live scraping."""
    return render_template("scrape.html", model_loaded=MODEL_LOADED)


@app.route("/scrape", methods=["POST"])
def scrape_process():
    """
    FR-SC-07: Panggil FastAPI scraper dan analisis hasilnya.
    """
    if not MODEL_LOADED:
        flash("Model AI belum berhasil dimuat.", "danger")
        return redirect(url_for("scrape"))
    
    # US-03.1: Ambil keyword dan limit dari form
    keyword = request.form.get("keyword", "").strip()
    if not keyword:
        flash("Kata kunci tidak boleh kosong.", "warning")
        return redirect(url_for("scrape"))
    
    # Sanitasi keyword
    keyword = str(escape(keyword))
    
    try:
        limit = int(request.form.get("limit", DEFAULT_SCRAPE_LIMIT))
        limit = max(10, min(limit, 500))  # Clamp antara 10 dan 500
    except (ValueError, TypeError):
        limit = DEFAULT_SCRAPE_LIMIT
    
    try:
        # FR-SC-07: Panggil FastAPI scraper dengan timeout 60 detik
        scraper_url = f"{SCRAPER_BASE_URL}{SCRAPER_ENDPOINT}"
        
        logger.info(f"Memanggil scraper: {scraper_url} | keyword: {keyword} | limit: {limit}")
        
        response = httpx.post(
            scraper_url,
            json={"keyword": keyword, "limit": limit},
            timeout=SCRAPER_TIMEOUT,
        )
        response.raise_for_status()
        
        scraper_data = response.json()
        
        if scraper_data.get("status") != "success":
            error_detail = scraper_data.get("message", "Tidak diketahui")
            flash(f"Scraping gagal: {error_detail}", "warning")
            return redirect(url_for("scrape"))
        
        tweets = scraper_data.get("data", [])
        
        if not tweets:
            flash(f"Tidak ditemukan data untuk kata kunci '{keyword}'. Coba kata kunci lain.", "info")
            return redirect(url_for("scrape"))
        
        # Analisis sentimen setiap tweet
        raw_texts = [t.get("text", "") for t in tweets]
        dates = [t.get("date", "") for t in tweets]
        
        clean_texts = [preprocess_text(text) for text in raw_texts]
        predictions = predict_batch(clean_texts)
        
        results = []
        for raw, clean, date, pred in zip(raw_texts, clean_texts, dates, predictions):
            results.append({
                "raw_text": raw,
                "clean_text": clean,
                "date": date,
                "predicted_label": pred.get("predicted_label", "Netral"),
                "confidence_positive": pred.get("confidence_positive", 0.0),
                "confidence_negative": pred.get("confidence_negative", 0.0),
                "confidence_neutral": pred.get("confidence_neutral", 0.0),
                "inference_time_ms": pred.get("inference_time_ms", 0.0),
            })
        
        # Siapkan data untuk dashboard
        summary = calculate_summary(results)
        chart_data = prepare_chart_data(results)
        valid_clean = [r["clean_text"] for r in results if r["clean_text"]]
        word_freq = get_word_frequencies(valid_clean)
        
        # Simpan di session untuk navigasi ke dashboard
        session["scrape_results"] = json.dumps(results[:200])  # Simpan max 200
        session["scrape_keyword"] = keyword
        session["scrape_summary"] = json.dumps(summary)
        session["scrape_chart"] = json.dumps(chart_data)
        session["scrape_word_freq"] = json.dumps(word_freq)
        
        context = {
            "results": results,
            "keyword": keyword,
            "summary": summary,
            "chart_data": json.dumps(chart_data),
            "word_freq": json.dumps(word_freq),
            "label_colors": LABEL_COLORS,
            "model_loaded": MODEL_LOADED,
            "scrape_count": scraper_data.get("count", len(results)),
        }
        
        return render_template("result_scrape.html", **context)
        
    except httpx.ConnectError:
        # NFR-R-02: Fallback jika FastAPI tidak tersedia
        logger.warning("FastAPI scraper tidak tersedia.")
        flash(
            "Layanan scraping tidak tersedia saat ini. "
            "Pastikan server scraper (port 8000) sudah berjalan.",
            "warning",
        )
        return redirect(url_for("scrape"))
        
    except httpx.TimeoutException:
        flash(
            f"Proses scraping melebihi batas waktu ({SCRAPER_TIMEOUT} detik). "
            "Coba kurangi jumlah data atau coba lagi nanti.",
            "warning",
        )
        return redirect(url_for("scrape"))
        
    except Exception as e:
        logger.error(f"Error saat scraping: {e}", exc_info=True)
        flash("Terjadi kesalahan saat proses scraping. Silakan coba lagi.", "danger")
        return redirect(url_for("scrape"))


# =============================================================
# ROUTE: Dashboard Visualisasi (EP-04)
# =============================================================

@app.route("/dashboard")
def dashboard():
    """
    EP-04: Dashboard visualisasi data dari hasil scraping atau batch.
    """
    # Cek apakah ada data dari sesi sebelumnya
    scrape_results_json = session.get("scrape_results")
    
    if not scrape_results_json:
        flash("Belum ada data untuk divisualisasikan. Lakukan analisis terlebih dahulu.", "info")
        return redirect(url_for("index"))
    
    try:
        results = json.loads(scrape_results_json)
        keyword = session.get("scrape_keyword", "")
        summary = json.loads(session.get("scrape_summary", "{}"))
        chart_data = session.get("scrape_chart", "{}")
        word_freq = session.get("scrape_word_freq", "{}")
        
        context = {
            "results": results,
            "keyword": keyword,
            "summary": summary,
            "chart_data": chart_data,
            "word_freq": word_freq,
            "label_colors": LABEL_COLORS,
            "model_loaded": MODEL_LOADED,
        }
        
        return render_template("dashboard.html", **context)
        
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error saat render dashboard: {e}")
        flash("Terjadi kesalahan saat menampilkan dashboard.", "danger")
        return redirect(url_for("index"))


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
        clean_text = preprocess_text(raw_text)
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


@app.route("/api/batch", methods=["POST"])
def api_batch():
    """JSON endpoint batch CSV — dipanggil SPA via fetch() + FormData."""
    if not MODEL_LOADED:
        return jsonify({"error": "Model belum dimuat."}), 503

    csv_file = request.files.get("csv_file")
    is_valid, error_msg, df = validate_csv(csv_file)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    text_col = detect_text_column(df)
    if text_col is None:
        return jsonify({"error": "Tidak dapat mendeteksi kolom teks."}), 400

    try:
        raw_texts   = df[text_col].fillna("").tolist()
        clean_texts = [preprocess_text(str(t).strip()) if str(t).strip() else "" for t in raw_texts]
        predictions = predict_batch(clean_texts)

        results = []
        for raw, clean, pred in zip(raw_texts, clean_texts, predictions):
            raw_str  = str(raw).strip()
            is_empty = not raw_str or not clean
            if is_empty:
                pred["skipped"] = True
            results.append({
                "raw_text":            raw_str,
                "clean_text":          clean,
                "predicted_label":     pred.get("predicted_label", "Netral"),
                "confidence_positive": pred.get("confidence_positive", 0.0),
                "confidence_negative": pred.get("confidence_negative", 0.0),
                "confidence_neutral":  pred.get("confidence_neutral",  0.0),
                "inference_time_ms":   pred.get("inference_time_ms",   0.0),
                "skipped":             pred.get("skipped", False),
            })

        summary    = calculate_summary(results)
        csv_output = generate_csv_output(results)
        return jsonify({
            "results":       results[:100],
            "total_results": len(results),
            "summary":       summary,
            "csv_content":   csv_output,
        })
    except Exception as e:
        logger.error(f"/api/batch error: {e}", exc_info=True)
        return jsonify({"error": "Terjadi kesalahan saat memproses CSV."}), 500


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    """JSON endpoint live scraping — dipanggil SPA via fetch(), menggunakan background task."""
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

    sources = body.get("sources", ["twitter", "web"])
    mode = body.get("mode", "live")
    try:
        days_back = int(body.get("days_back", DEFAULT_DAYS_BACK))
        days_back = max(1, min(days_back, 30))
    except (ValueError, TypeError):
        days_back = DEFAULT_DAYS_BACK

    # Pipeline punya fallback in-process jika scraper eksternal tidak tersedia
    from pipeline import start_scrape_pipeline
    try:
        req_id = start_scrape_pipeline(keyword, limit, sources, mode=mode, days_back=days_back)
        return jsonify({"status": "ok", "req_id": req_id})
    except Exception as e:
        logger.error(f"/api/scrape pipeline error: {e}", exc_info=True)
        return jsonify({"error": "Terjadi kesalahan saat memulai scraping."}), 500


# =============================================================
@app.route("/api/status/<req_id>", methods=["GET"])
def api_status(req_id):
    from pipeline import get_status
    status_data = get_status(req_id)
    return jsonify(status_data)

@app.route("/api/results/precomputed", methods=["GET"])
def api_precomputed():
    import os, pandas as pd
    from utils import get_overall_distribution, get_timeline_data, get_top_items
    file_path = os.path.join("data", "precomputed_large.csv")
    if not os.path.exists(file_path):
        return jsonify({"error": "Pre-computed data not found."}), 404
    df = pd.read_csv(file_path)
    from config import MODEL_METRICS
    return jsonify({
        "distribution": get_overall_distribution(df),
        "timeline": get_timeline_data(df),
        "top_items": get_top_items(df, n=100),
        "model_metrics": MODEL_METRICS
    })

@app.route("/api/results/<req_id>", methods=["GET"])
def api_results(req_id):
    from pipeline import get_status
    status_data = get_status(req_id)
    if status_data.get("status") == "COMPLETED" and status_data.get("file_path"):
        import pandas as pd
        from utils import get_overall_distribution, get_timeline_data, get_top_items, filter_df_by_days, get_word_freq_for_df
        from config import MODEL_METRICS

        file_path = status_data["file_path"]
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            logger.error(f"Failed to read CSV {file_path}: {e}")
            return jsonify({"error": "Gagal membaca file hasil."}), 500

        # Parse optional time-range filter
        days_param = request.args.get('days')
        days = int(days_param) if days_param and days_param.isdigit() else None
        df_filtered = filter_df_by_days(df, days) if days is not None else df

        # Normalize column names: rename Indonesian to English for compatibility
        col_map = {
            "teks_asli": "raw_text",
            "teks_bersih": "clean_text",
            "sentimen": "sentimen",  # keep as-is for aggregation
            "confidence_positif": "confidence_positive",
            "confidence_negatif": "confidence_negative",
            "confidence_netral": "confidence_neutral",
        }
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # top_items and confidence_avg always from full df (for data table & model overview)
        top_items_raw = get_top_items(df, n=100)
        top_items = []
        for item in top_items_raw:
            top_items.append({
                "raw_text": item.get("teks_asli", ""),
                "source": item.get("source", ""),
                "date": str(item.get("date", "")),
                "predicted_label": item.get("sentimen", ""),
                "confidence_positive": float(item.get("confidence_positif", item.get("confidence", 0))),
                "confidence_negative": float(item.get("confidence_negatif", 0)),
                "confidence_neutral": float(item.get("confidence_netral", 0)),
            })

        confidence_avg = {
            "positive": round(float(df["confidence_positif"].mean()) * 100, 1) if "confidence_positif" in df.columns else 0.0,
            "neutral":  round(float(df["confidence_netral"].mean())  * 100, 1) if "confidence_netral"  in df.columns else 0.0,
            "negative": round(float(df["confidence_negatif"].mean()) * 100, 1) if "confidence_negatif" in df.columns else 0.0,
        }

        # timeline, distribution, and word_freq respect the active date filter
        dist = get_overall_distribution(df_filtered)
        return jsonify({
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
            "total_results":  status_data.get("total_results", len(df)),
        })
    return jsonify({"error": "Results not ready or not found."}), 404


# Error Handlers (NFR-S-05)
# =============================================================

@app.errorhandler(413)
def too_large(e):
    flash("Berkas yang diunggah terlalu besar. Maksimum ukuran berkas adalah 16 MB.", "warning")
    return redirect(url_for("batch")), 413


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
    )
