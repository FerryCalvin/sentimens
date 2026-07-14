# ============================================================
# utils.py — Helper Functions
# ============================================================
import io
import os
import csv
import logging
from collections import Counter, OrderedDict

import pandas as pd
from markupsafe import escape

from config import CSV_OUTPUT_COLUMNS

# LRU cache with a hard cap — evicts the oldest entry when full.
# Values are (stat_key, data) tuples for path-keyed/request_id-keyed entries below,
# EXCEPT the dead `get_results()` aggregation path further down, which stores plain
# dicts under bare request_id keys in `_results_cache` (different key shape, never
# collides with the file-path keys used by `load_results_from_csv`).
_CACHE_MAX_SIZE = 50
_results_cache: OrderedDict = OrderedDict()
_df_cache: OrderedDict = OrderedDict()


def _stat_key(file_path: str) -> tuple[float, int] | None:
    """(mtime, size) fingerprint of a file, used to detect on-disk changes for cache invalidation."""
    try:
        st = os.stat(file_path)
        return (st.st_mtime, st.st_size)
    except OSError:
        return None


def _available_output_columns(file_path: str) -> list[str]:
    """Intersect CSV_OUTPUT_COLUMNS with a file's actual header, so older result
    CSVs written before new columns existed (e.g. 'dilewati') still load fine."""
    with open(file_path, encoding="utf-8-sig") as f:
        header = next(csv.reader(f))
    return [c for c in CSV_OUTPUT_COLUMNS if c in header]

CSV_DTYPES = {
    "teks_asli": "string",
    "teks_bersih": "string",
    "sentimen": "category",
    "confidence_positif": "float32",
    "confidence_negatif": "float32",
    "confidence_netral": "float32",
}


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


def remove_outliers_and_duplicates(items: list[dict], text_key: str = "raw_text") -> tuple[list[dict], dict]:
    """
    Bersihkan hasil scraping mentah dari duplikat dan outlier sebelum masuk ke pipeline
    preprocessing/inferensi.

    Menangani tiga kondisi umum data hasil scraping yang "kotor":
    1. Duplikat: retweet/repost dengan teks identik (dibandingkan setelah normalisasi
       strip + lowercase), kemunculan pertama yang dipertahankan.
    2. Teks kosong/terlalu pendek: fragmen yang gagal ke-scrape dengan benar (< 3 karakter).
    3. Outlier panjang teks: dideteksi dengan metode IQR (Q1 - 1.5*IQR s/d Q3 + 1.5*IQR)
       pada panjang karakter, menangkap fragmen yang rusak (terlalu pendek) atau teks yang
       tercampur/berlebihan (terlalu panjang) dibanding mayoritas hasil scraping. Langkah ini
       hanya dijalankan jika data tersisa >= 20 baris, karena IQR tidak reliabel pada sampel kecil.

    Returns:
        (filtered_items, stats) — stats berisi jumlah baris yang dibuang per kategori.
    """
    total_before = len(items)

    seen = set()
    deduped = []
    duplicates_removed = 0
    for item in items:
        norm = str(item.get(text_key, "")).strip().lower()
        if norm and norm in seen:
            duplicates_removed += 1
            continue
        seen.add(norm)
        deduped.append(item)

    non_empty = []
    empty_removed = 0
    for item in deduped:
        if len(str(item.get(text_key, "")).strip()) < 3:
            empty_removed += 1
            continue
        non_empty.append(item)

    outliers_removed = 0
    final_items = non_empty
    if len(non_empty) >= 20:
        lengths = sorted(len(str(item.get(text_key, "")).strip()) for item in non_empty)
        q1 = lengths[int(len(lengths) * 0.25)]
        q3 = lengths[int(len(lengths) * 0.75)]
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        final_items = []
        for item in non_empty:
            length = len(str(item.get(text_key, "")).strip())
            if length < lower_bound or length > upper_bound:
                outliers_removed += 1
                continue
            final_items.append(item)

    stats = {
        "duplicates_removed": duplicates_removed,
        "empty_removed": empty_removed,
        "outliers_removed": outliers_removed,
        "total_before": total_before,
        "total_after": len(final_items),
    }
    return final_items, stats


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
            "confidence_positif": round(float(result.get("confidence_positive", 0.0) or 0.0), 6),
            "confidence_negatif": round(float(result.get("confidence_negative", 0.0) or 0.0), 6),
            "confidence_netral": round(float(result.get("confidence_neutral", 0.0) or 0.0), 6),
            "source": result.get("source", ""),
            "date": result.get("date", ""),
            "dilewati": result.get("skipped", False),
            "alasan_dilewati": result.get("skip_reason", ""),
        })
    
    return output.getvalue()

def load_results_from_csv(file_path: str) -> list[dict]:
    """
    Muat hasil dari CSV dengan caching memory dan DTYPE optimization.
    Ini menjamin pemuatan ke memori di bawah 3 detik.
    """
    stat_key = _stat_key(file_path)
    cached = _results_cache.get(file_path)
    if cached is not None and stat_key is not None and cached[0] == stat_key:
        _results_cache.move_to_end(file_path)  # LRU: mark as recently used
        return cached[1]

    try:
        df = pd.read_csv(
            file_path,
            dtype=CSV_DTYPES,
            usecols=_available_output_columns(file_path),
            engine='c'
        )
        df = df.rename(columns={
            "teks_asli": "raw_text",
            "teks_bersih": "clean_text",
            "sentimen": "predicted_label",
            "confidence_positif": "confidence_positive",
            "confidence_negatif": "confidence_negative",
            "confidence_netral": "confidence_neutral",
            "dilewati": "skipped",
            "alasan_dilewati": "skip_reason",
        })
        # "predicted_label" is read as category dtype (CSV_DTYPES) — a category column
        # can't be filled with a value outside its observed categories (e.g. a small
        # batch with no "Netral" rows), so widen it before fillna.
        if "predicted_label" in df.columns:
            df["predicted_label"] = df["predicted_label"].astype(object)
        # Replace NaN/None values to ensure valid JSON serialization (no NaNs inside list of dicts)
        df = df.fillna({
            "raw_text": "",
            "clean_text": "",
            "predicted_label": "Netral",
            "confidence_positive": 0.0,
            "confidence_negative": 0.0,
            "confidence_neutral": 0.0,
            "source": "",
            "date": "",
            "skipped": False,
            "skip_reason": "",
        })
        results = df.to_dict('records')
        _NULL_STRINGS = {'nan', 'NaT', '<NA>'}
        for r in results:
            # Text/date/source: also strip string sentinels emitted by Pandas
            for k in ["raw_text", "clean_text", "predicted_label", "source", "date", "skip_reason"]:
                val = r.get(k)
                if val is None:
                    r[k] = ""
                elif isinstance(val, str):
                    if val in _NULL_STRINGS:
                        r[k] = ""
                elif pd.isna(val):
                    r[k] = ""
            # Numeric confidence: only replace non-string nulls
            for k in ["confidence_positive", "confidence_negative", "confidence_neutral"]:
                val = r.get(k)
                if not isinstance(val, str) and (val is None or pd.isna(val)):
                    r[k] = 0.0
            r["skipped"] = bool(r.get("skipped", False))

        _results_cache[file_path] = (stat_key, results)
        if len(_results_cache) > _CACHE_MAX_SIZE:
            _results_cache.popitem(last=False)  # evict least recently used
        return results
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")
        return []


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

# --- PHASE 3 PANDAS FUNCTIONS ---
from config import CSV_OUTPUT_COLUMNS

def _resolve_csv_path(request_id: str) -> str | None:
    """Resolve a request_id to its on-disk CSV path, applying the 'precomputed' fallback."""
    path = f'data/{request_id}.csv'
    if os.path.exists(path):
        return path
    if request_id == "precomputed" and os.path.exists('data/precomputed_large.csv'):
        return 'data/precomputed_large.csv'
    return None

def load_dataframe(request_id: str) -> pd.DataFrame:
    """Load CSV dengan dtype eksplisit dan kolom selektif untuk performa optimal."""
    path = _resolve_csv_path(request_id)
    if path is None:
        return pd.DataFrame()

    return pd.read_csv(
        path,
        dtype=CSV_DTYPES,
        usecols=_available_output_columns(path),
        parse_dates=['date'],
        engine='c'
    )

def load_dataframe_cached(request_id: str) -> pd.DataFrame:
    """Load DataFrame with LRU cache to avoid redundant disk I/O on repeated polls."""
    path = _resolve_csv_path(request_id)
    stat_key = _stat_key(path) if path else None
    cached = _df_cache.get(request_id)
    if cached is not None and stat_key is not None and cached[0] == stat_key:
        _df_cache.move_to_end(request_id)
        return cached[1]
    df = load_dataframe(request_id)
    if not df.empty:
        _df_cache[request_id] = (stat_key, df)
        if len(_df_cache) > _CACHE_MAX_SIZE:
            _df_cache.popitem(last=False)
    return df

def get_results(request_id: str) -> dict:
    """Return cached aggregated results, atau hitung dan cache jika belum ada."""
    if request_id not in _results_cache:
        df = load_dataframe(request_id)
        if df.empty:
            return {}
        _results_cache[request_id] = build_results(df)
        if len(_results_cache) > _CACHE_MAX_SIZE:
            _results_cache.popitem(last=False)
    return _results_cache[request_id]

def build_results(df: pd.DataFrame) -> dict:
    """Aggregasi tunggal: jalankan semua operasi pandas dalam satu pass."""
    return {
        'distribution': build_distribution(df),
        'timeline':     build_timeline(df),
        'top_items':    get_top_items(df),
    }

def build_timeline(df: pd.DataFrame) -> dict:
    if 'date' not in df.columns or df.empty:
        return {}
    grouped = df.groupby([df['date'].dt.date, 'sentimen'], observed=False).size().unstack(fill_value=0)
    for col in ['Positif', 'Netral', 'Negatif']:
        if col not in grouped.columns:
            grouped[col] = 0
            
    result = {}
    for date, row in grouped.to_dict(orient='index').items():
        result[str(date)] = {
            "Positif": int(row.get('Positif', 0)),
            "Netral":  int(row.get('Netral',  0)),
            "Negatif": int(row.get('Negatif', 0)),
        }
    return result

def build_distribution(df: pd.DataFrame) -> dict:
    if df.empty:
        return {'positive': 0, 'neutral': 0, 'negative': 0, 'total': 0}
    counts = df['sentimen'].value_counts()
    return {
        'positive': int(counts.get('Positif', 0)),
        'neutral':  int(counts.get('Netral', 0)),
        'negative': int(counts.get('Negatif', 0)),
        'total': len(df)
    }

def get_overall_distribution(df: pd.DataFrame) -> dict:
    """Alias untuk build_distribution — dipakai oleh /api/results endpoints."""
    return build_distribution(df)


def _days_cutoff(days: int) -> pd.Timestamp:
    return pd.Timestamp.now() - pd.Timedelta(days=days)


def filter_df_by_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """Return rows from the last `days` days based on the `date` column."""
    if 'date' not in df.columns or df.empty:
        return df
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    if df['date'].dt.tz is not None:
        df['date'] = df['date'].dt.tz_localize(None)
    cutoff = _days_cutoff(days)
    return df[df['date'] >= cutoff]


def get_word_freq_for_df(df: pd.DataFrame) -> list:
    """Return [[word, count], ...] top-50 from teks_bersih column."""
    from preprocessing import get_word_frequencies
    if df.empty or 'teks_bersih' not in df.columns:
        return []
    texts = df['teks_bersih'].dropna().tolist()
    freq_dict = get_word_frequencies(texts)
    return [[word, count] for word, count in list(freq_dict.items())[:50]]


def choose_timeline_granularity(days: int | None) -> str:
    """Pick a chart bucket size so long ranges don't render as sparse per-day points."""
    if days is None or days > 180:
        return "month"
    if days > 31:
        return "week"
    return "day"


def get_timeline_data(df: pd.DataFrame, days: int | None = None, granularity: str | None = None) -> list:
    """
    Konversi timeline dict ke format list yang dipakai frontend SPA.
    Buckets by day/week/month (via `granularity`, auto-picked from `days` if omitted)
    and zero-fills empty buckets so long ranges render as a continuous series.
    Returns list of {date, positive, negative, neutral}.
    """
    if 'date' not in df.columns or df.empty:
        return []

    try:
        granularity = granularity or choose_timeline_granularity(days)

        # Pastikan kolom date sudah datetime
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df = df.copy()
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        if df.empty:
            return []

        if granularity == "week":
            bucket_key = df['date'].dt.to_period('W-MON').dt.start_time
            freq = 'W-MON'
        elif granularity == "month":
            bucket_key = df['date'].dt.to_period('M').dt.start_time
            freq = 'MS'
        else:
            bucket_key = df['date'].dt.normalize()
            freq = 'D'

        grouped = df.groupby([bucket_key, 'sentimen'], observed=False).size().unstack(fill_value=0)
        for col in ['Positif', 'Netral', 'Negatif']:
            if col not in grouped.columns:
                grouped[col] = 0

        range_end = pd.Timestamp.now().normalize()
        range_start = _days_cutoff(days).normalize() if days else df['date'].min().normalize()
        if range_start > range_end:
            range_start = range_end
        # Snap range_start to the bucket boundary — pd.date_range(freq='MS'/'W-MON') only emits
        # dates ON that boundary, so an unaligned start silently drops the first partial bucket.
        if granularity == "week":
            range_start = range_start.to_period('W-MON').start_time
        elif granularity == "month":
            range_start = range_start.to_period('M').start_time
        full_index = pd.date_range(range_start, range_end, freq=freq)
        if len(full_index) > 0:
            grouped = grouped.reindex(full_index, fill_value=0)

        result = []
        for date_val, row in grouped.to_dict(orient='index').items():
            result.append({
                "date":     pd.Timestamp(date_val).date().isoformat(),
                "positive": int(row.get('Positif', 0)),
                "neutral":  int(row.get('Netral',  0)),
                "negative": int(row.get('Negatif', 0)),
            })
        return result
    except Exception as e:
        logger.error(f"Error building timeline: {e}")
        return []


def compute_confidence_avg(df: pd.DataFrame) -> dict:
    """Rata-rata confidence per kelas (dalam persen). Dipakai oleh JSON API dan export laporan."""
    def safe_mean_pct(series):
        if series.empty:
            return 0.0
        val = series.mean()
        if pd.isna(val):
            return 0.0
        return round(float(val) * 100, 1)

    return {
        "positive": safe_mean_pct(df["confidence_positif"]) if "confidence_positif" in df.columns else 0.0,
        "neutral":  safe_mean_pct(df["confidence_netral"])  if "confidence_netral"  in df.columns else 0.0,
        "negative": safe_mean_pct(df["confidence_negatif"]) if "confidence_negatif" in df.columns else 0.0,
    }


def get_top_items(df: pd.DataFrame, n: int = 100) -> list:
    if df.empty:
        return []
    df = df.copy()
    df['confidence_positif'] = df['confidence_positif'].fillna(0.0)
    df['confidence_negatif'] = df['confidence_negatif'].fillna(0.0)
    df['confidence_netral'] = df['confidence_netral'].fillna(0.0)

    df['confidence'] = df[[
        'confidence_positif', 'confidence_netral', 'confidence_negatif'
    ]].max(axis=1)

    cols = []
    for c in ['teks_asli', 'teks_bersih', 'source', 'date', 'sentimen',
              'confidence_positif', 'confidence_negatif', 'confidence_netral', 'confidence',
              'dilewati', 'alasan_dilewati']:
        if c in df.columns:
            cols.append(c)

    raw_items = df.nlargest(n, 'confidence')[cols].to_dict('records')

    # Clean up any NaN/NaT values in the final dict list to ensure strict JSON compatibility
    _NULL_STRINGS = {'nan', 'NaT', '<NA>'}
    cleaned_items = []
    for item in raw_items:
        cleaned_item = {}
        for k, v in item.items():
            if v is None:
                cleaned_item[k] = 0.0 if k in ('confidence_positif', 'confidence_negatif', 'confidence_netral', 'confidence') else (
                    'Netral' if k == 'sentimen' else '')
            elif isinstance(v, str):
                # Catch string sentinels (Pandas string dtype emits these)
                if v in _NULL_STRINGS:
                    cleaned_item[k] = 0.0 if k in ('confidence_positif', 'confidence_negatif', 'confidence_netral', 'confidence') else (
                        'Netral' if k == 'sentimen' else '')
                else:
                    cleaned_item[k] = v
            elif pd.isna(v):
                cleaned_item[k] = 0.0 if k in ('confidence_positif', 'confidence_negatif', 'confidence_netral', 'confidence') else (
                    'Netral' if k == 'sentimen' else '')
            else:
                cleaned_item[k] = v
        cleaned_items.append(cleaned_item)

    return cleaned_items


def compute_evaluation_metrics(true_labels: list, pred_labels: list) -> dict:
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
    labels = ["Negatif", "Netral", "Positif"]
    acc = accuracy_score(true_labels, pred_labels)
    p, r, f1, support = precision_recall_fscore_support(
        true_labels, pred_labels, labels=labels, average=None, zero_division=0
    )
    cm = confusion_matrix(true_labels, pred_labels, labels=labels)
    return {
        "accuracy": round(acc * 100, 2),
        "macro": {
            "precision": round(float(p.mean()) * 100, 2),
            "recall":    round(float(r.mean()) * 100, 2),
            "f1":        round(float(f1.mean()) * 100, 2),
        },
        "per_class": {
            labels[i]: {
                "precision": round(float(p[i]) * 100, 2),
                "recall":    round(float(r[i]) * 100, 2),
                "f1":        round(float(f1[i]) * 100, 2),
                "support":   int(support[i]),
            }
            for i in range(len(labels))
        },
        "confusion_matrix": cm.tolist(),
    }
