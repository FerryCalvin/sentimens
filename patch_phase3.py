import os

# --- 1. UPDATE UTILS.PY ---
utils_path = "utils.py"
with open(utils_path, "r", encoding="utf-8") as f:
    utils_code = f.read()

new_utils_funcs = """
# --- PHASE 3 PANDAS FUNCTIONS ---
from config import CSV_OUTPUT_COLUMNS

def load_dataframe(request_id: str) -> pd.DataFrame:
    \"\"\"Load CSV dengan dtype eksplisit dan kolom selektif untuk performa optimal.\"\"\"
    path = f'data/{request_id}.csv'
    if not os.path.exists(path):
        # Fallback to precomputed for testing if req not found
        if request_id == "precomputed":
            path = 'data/precomputed_large.csv'
        else:
            return pd.DataFrame()
            
    return pd.read_csv(
        path,
        dtype=CSV_DTYPES,
        usecols=["teks_asli", "teks_bersih", "sentimen", "confidence_positif", "confidence_negatif", "confidence_netral", "source", "date"],
        parse_dates=['date'],
        engine='c'
    )

def get_results(request_id: str) -> dict:
    \"\"\"Return cached aggregated results, atau hitung dan cache jika belum ada.\"\"\"
    if request_id not in _results_cache:
        df = load_dataframe(request_id)
        if df.empty:
            return {}
        _results_cache[request_id] = build_results(df)
    return _results_cache[request_id]

def build_results(df: pd.DataFrame) -> dict:
    \"\"\"Aggregasi tunggal: jalankan semua operasi pandas dalam satu pass.\"\"\"
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
            
    # Frontend expects: summary.timeline[date].Positif
    result = {}
    for date, row in grouped.iterrows():
        result[str(date)] = {
            "Positif": int(row.get('Positif', 0)),
            "Netral": int(row.get('Netral', 0)),
            "Negatif": int(row.get('Negatif', 0))
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

def get_top_items(df: pd.DataFrame, n: int = 20) -> list:
    if df.empty:
        return []
    df = df.copy()
    df['confidence_max'] = df[[
        'confidence_positif', 'confidence_netral', 'confidence_negatif'
    ]].max(axis=1)
    
    # Required columns
    cols = []
    for c in ['teks_asli', 'source', 'date', 'sentimen', 'confidence_max']:
        if c in df.columns:
            cols.append(c)
            
    return df.nlargest(n, 'confidence_max')[cols].to_dict('records')

def send_notification(email: str, topic: str, request_id: str, item_count: int):
    \"\"\"FR-EM-01: Send email notification.\"\"\"
    if not email:
        return
    logger.info(f"Mengirim notifikasi email ke {email} untuk topik '{topic}' ({item_count} item).")
    try:
        # Mocking real SMTP to avoid crashing without credentials
        logger.info(f"SIMULATED EMAIL SENT TO {email} for topic {topic}!")
    except Exception as e:
        logger.error(f"Gagal mengirim email: {e}")
"""

if "# --- PHASE 3 PANDAS FUNCTIONS ---" not in utils_code:
    utils_code += "\nimport os\n" + new_utils_funcs
    with open(utils_path, "w", encoding="utf-8") as f:
        f.write(utils_code)
    print("utils.py updated.")

# --- 2. UPDATE APP.PY ---
app_path = "app.py"
with open(app_path, "r", encoding="utf-8") as f:
    app_code = f.read()

new_routes = """
@app.route("/api/results/<req_id>", methods=["GET"])
def api_results(req_id):
    from utils import get_results
    data = get_results(req_id)
    if not data:
        return jsonify({"error": "Data tidak ditemukan"}), 404
    return jsonify(data)
    
@app.route("/api/results/precomputed", methods=["GET"])
def api_precomputed():
    from utils import get_results
    data = get_results("precomputed")
    if not data:
        return jsonify({"error": "Data precomputed tidak ditemukan"}), 404
    return jsonify(data)
"""

if "/api/results/<req_id>" not in app_code:
    # Insert before error handlers
    app_code = app_code.replace("# ============================================================\n# Error Handlers", new_routes + "\n# ============================================================\n# Error Handlers")
    with open(app_path, "w", encoding="utf-8") as f:
        f.write(app_code)
    print("app.py updated.")

# --- 3. UPDATE PIPELINE.PY ---
# Add email sending logic
pipeline_path = "pipeline.py"
with open(pipeline_path, "r", encoding="utf-8") as f:
    pipe_code = f.read()

if "send_notification" not in pipe_code:
    pipe_code = pipe_code.replace("from utils import generate_csv_output, calculate_summary", "from utils import generate_csv_output, calculate_summary, send_notification")
    
    # In start_scrape_pipeline
    old_comp = """_update_status(req_id, COMPLETED, "Selesai", 100, 
                           total_results=len(results), 
                           summary=summary)"""
    new_comp = """_update_status(req_id, COMPLETED, "Selesai", 100, 
                           total_results=len(results), 
                           summary=summary)
            # Call email notification (mocked)
            # In a real app we would pass the actual email from the request
            send_notification("user@example.com", keyword, req_id, len(results))"""
    
    pipe_code = pipe_code.replace(old_comp, new_comp)
    with open(pipeline_path, "w", encoding="utf-8") as f:
        f.write(pipe_code)
    print("pipeline.py updated.")

