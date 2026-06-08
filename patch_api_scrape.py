with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
# Find the api_scrape function
match = re.search(r'@app\.route\("/api/scrape", methods=\["POST"\]\)\ndef api_scrape\(\):.*?(?=@app\.route)', content, re.DOTALL)
if match:
    old_func = match.group(0)
    new_func = '''@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    """JSON endpoint live scraping — menjalankan background pipeline."""
    if not MODEL_LOADED:
        return jsonify({"error": "Model belum dimuat."}), 503

    body = request.get_json(force=True, silent=True) or {}
    keyword = str(body.get("keyword", "")).strip()
    if not keyword:
        return jsonify({"error": "Kata kunci tidak boleh kosong."}), 400

    keyword = str(escape(keyword))
    try:
        limit = int(body.get("limit", DEFAULT_SCRAPE_LIMIT))
        limit = max(10, min(limit, 500))
    except (ValueError, TypeError):
        limit = DEFAULT_SCRAPE_LIMIT
        
    sources = body.get("sources", ["twitter", "news"])
    mode = str(body.get("mode", "demo"))

    try:
        from pipeline import start_scrape_pipeline
        req_id = start_scrape_pipeline(keyword, limit, sources, mode=mode)
        return jsonify({"req_id": req_id, "status": "PENDING"})
    except Exception as e:
        logger.error(f"/api/scrape error: {e}", exc_info=True)
        return jsonify({"error": "Terjadi kesalahan saat memulai scraping."}), 500

'''
    content = content.replace(old_func, new_func)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced api_scrape in app.py successfully")
else:
    print("Could not find api_scrape function block")
