with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if line.startswith('@app.route("/api/scrape"'):
        start_idx = i
        break

if start_idx != -1:
    for i in range(start_idx + 1, len(lines)):
        if lines[i].startswith('@app.route'):
            end_idx = i
            break
    if end_idx == -1:
        end_idx = len(lines)

    new_func = '''@app.route("/api/scrape", methods=["POST"])
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
    
    new_lines = lines[:start_idx] + [new_func] + lines[end_idx:]
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Replaced api_scrape successfully.")
else:
    print("Failed to find api_scrape.")
