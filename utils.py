# ============================================================
# utils.py — Helper Functions
# ============================================================
import io
import csv
import json
import logging
from datetime import datetime
from collections import Counter

import pandas as pd
from markupsafe import escape

from config import CSV_OUTPUT_COLUMNS, LABEL_COLORS

logger = logging.getLogger(__name__)


def sanitize_input(text: str) -> str:
    """
    NFR-S-02: Sanitasi input pengguna untuk mencegah XSS.
    Menggunakan markupsafe.escape() sesuai persyaratan keamanan.
    """
    if not text:
        return ""
    return str(escape(str(text)))


def validate_csv(file_storage) -> tuple[bool, str, pd.DataFrame | None]:
    """
    FR-BT-02: Validasi berkas CSV yang diunggah.
    
    Returns:
        (is_valid, error_message, dataframe)
    """
    if file_storage is None:
        return False, "Tidak ada berkas yang diunggah.", None
    
    filename = file_storage.filename
    if not filename or not filename.lower().endswith(".csv"):
        return False, "Hanya berkas dengan ekstensi .csv yang diterima.", None
    
    try:
        # Baca konten berkas
        content = file_storage.read()
        if not content:
            return False, "Berkas CSV tidak boleh kosong.", None
        
        # Reset pointer berkas
        file_storage.seek(0)
        
        # Coba parse sebagai CSV
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(content), encoding="latin-1")
        
        if df.empty:
            return False, "Berkas CSV tidak memiliki baris data.", None
        
        if len(df.columns) == 0:
            return False, "Berkas CSV tidak memiliki kolom yang valid.", None
        
        return True, "", df
        
    except Exception as e:
        logger.error(f"Error validasi CSV: {e}")
        return False, f"Berkas CSV tidak dapat dibaca. Pastikan format CSV valid.", None


def detect_text_column(df: pd.DataFrame) -> str | None:
    """
    Deteksi kolom teks secara otomatis dari DataFrame.
    Prioritaskan kolom bernama 'text', 'teks', 'tweet', 'content', 'review'.
    Jika tidak ada, gunakan kolom pertama.
    
    Returns:
        Nama kolom teks, atau None jika tidak ditemukan
    """
    priority_names = [
        "text", "teks", "tweet", "content", "review",
        "komentar", "ulasan", "kalimat", "sentence",
        "data", "tweet_text", "full_text", "body",
    ]
    
    cols_lower = {col.lower(): col for col in df.columns}
    
    for name in priority_names:
        if name in cols_lower:
            return cols_lower[name]
    
    # Gunakan kolom pertama sebagai fallback
    return df.columns[0] if len(df.columns) > 0 else None


def generate_csv_output(results: list[dict]) -> str:
    """
    FR-BT-05: Generate CSV hasil analisis batch.
    
    Args:
        results: List dict hasil analisis dengan key:
                 raw_text, clean_text, predicted_label,
                 confidence_positive, confidence_negative, confidence_neutral
    
    Returns:
        String CSV yang dapat diunduh
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=CSV_OUTPUT_COLUMNS,
        extrasaction="ignore",
    )
    writer.writeheader()
    
    for result in results:
        writer.writerow({
            "teks_asli": result.get("raw_text", ""),
            "teks_bersih": result.get("clean_text", ""),
            "sentimen": result.get("predicted_label", ""),
            "confidence_positif": result.get("confidence_positive", 0.0),
            "confidence_negatif": result.get("confidence_negative", 0.0),
            "confidence_netral": result.get("confidence_neutral", 0.0),
        })
    
    return output.getvalue()


def calculate_summary(results: list[dict]) -> dict:
    """
    FR-BT-06: Hitung ringkasan statistik dari hasil analisis.
    
    Returns:
        dict dengan total, per-kelas count & percentage
    """
    total = len(results)
    if total == 0:
        return {
            "total": 0,
            "positif": 0,
            "negatif": 0,
            "netral": 0,
            "positif_pct": 0.0,
            "negatif_pct": 0.0,
            "netral_pct": 0.0,
            "invalid": 0,
        }
    
    label_counts = Counter(r.get("predicted_label", "Netral") for r in results)
    invalid_count = sum(1 for r in results if r.get("skipped", False))
    valid_total = total - invalid_count
    
    positif = label_counts.get("Positif", 0)
    negatif = label_counts.get("Negatif", 0)
    netral = label_counts.get("Netral", 0)
    
    return {
        "total": total,
        "valid": valid_total,
        "positif": positif,
        "negatif": negatif,
        "netral": netral,
        "positif_pct": round((positif / total * 100) if total > 0 else 0, 1),
        "negatif_pct": round((negatif / total * 100) if total > 0 else 0, 1),
        "netral_pct": round((netral / total * 100) if total > 0 else 0, 1),
        "invalid": invalid_count,
    }


def prepare_chart_data(results: list[dict]) -> dict:
    """
    Siapkan data untuk Chart.js (line chart dan pie chart).
    
    Returns:
        dict dengan data untuk setiap tipe grafik
    """
    # Pie chart data (FR-VZ-02)
    summary = calculate_summary(results)
    pie_data = {
        "labels": ["Positif", "Negatif", "Netral"],
        "data": [summary["positif"], summary["negatif"], summary["netral"]],
        "colors": [
            LABEL_COLORS["Positif"],
            LABEL_COLORS["Negatif"],
            LABEL_COLORS["Netral"],
        ],
    }
    
    # Line chart data — distribusi berdasarkan urutan waktu/index (FR-VZ-01)
    # Kelompokkan berdasarkan tanggal jika tersedia, atau per-10 data
    line_data = _prepare_line_chart_data(results)
    
    return {
        "pie": pie_data,
        "line": line_data,
        "summary": summary,
    }


def _prepare_line_chart_data(results: list[dict]) -> dict:
    """
    Siapkan data line chart: distribusi sentimen berdasarkan waktu atau index.
    """
    if not results:
        return {"labels": [], "positif": [], "negatif": [], "netral": []}
    
    # Cek apakah ada data tanggal
    has_dates = any(r.get("date") for r in results)
    
    if has_dates:
        # Kelompokkan berdasarkan tanggal (hari)
        from collections import defaultdict
        date_groups: dict[str, list] = defaultdict(list)
        
        for r in results:
            date_str = r.get("date", "")
            try:
                # Parse ISO 8601 date
                if date_str:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    key = dt.strftime("%d/%m")
                else:
                    key = "Tidak Diketahui"
            except (ValueError, AttributeError):
                key = date_str[:10] if date_str else "Tidak Diketahui"
            
            date_groups[key].append(r.get("predicted_label", "Netral"))
        
        labels = sorted(date_groups.keys())
        positif_counts = []
        negatif_counts = []
        netral_counts = []
        
        for lbl in labels:
            items = date_groups[lbl]
            positif_counts.append(items.count("Positif"))
            negatif_counts.append(items.count("Negatif"))
            netral_counts.append(items.count("Netral"))
        
    else:
        # Tidak ada tanggal: kelompokkan per-10 item
        chunk_size = max(1, len(results) // 10) if len(results) > 10 else 1
        labels = []
        positif_counts = []
        negatif_counts = []
        netral_counts = []
        
        for i in range(0, len(results), chunk_size):
            chunk = results[i : i + chunk_size]
            chunk_labels = [r.get("predicted_label", "Netral") for r in chunk]
            labels.append(f"Data {i+1}–{min(i+chunk_size, len(results))}")
            positif_counts.append(chunk_labels.count("Positif"))
            negatif_counts.append(chunk_labels.count("Negatif"))
            netral_counts.append(chunk_labels.count("Netral"))
    
    return {
        "labels": labels,
        "positif": positif_counts,
        "negatif": negatif_counts,
        "netral": netral_counts,
    }


def format_confidence(value: float) -> str:
    """Format confidence score sebagai persentase string."""
    return f"{value * 100:.1f}%"


def get_confidence_badge_class(label: str) -> str:
    """
    Dapatkan Bootstrap badge class berdasarkan label sentimen.
    Sesuai FR-VZ-05 skema warna.
    """
    badge_map = {
        "Positif": "success",
        "Negatif": "danger",
        "Netral": "secondary",
    }
    return badge_map.get(label, "secondary")
