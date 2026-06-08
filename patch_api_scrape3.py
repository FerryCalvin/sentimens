with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

match = re.search(r'(@app\.route\("/api/scrape", methods=\["POST"\]\)\ndef api_scrape\(\):.*?)# =============================================================\n# Error Handlers \(NFR-S-05\)', content, re.DOTALL)

if match:
    old_block = match.group(1)
    new_block = '''@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    """JSON endpoint live scraping."""
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
    content = content.replace(old_block, new_block)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced api_scrape body")
else:
    print("Could not find the block to replace")
