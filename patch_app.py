with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_str = '''    sources = body.get("sources", ["twitter", "news"])

    try:
        req_id = start_scrape_pipeline(keyword, limit, sources)
        return jsonify({"req_id": req_id, "status": "PENDING"})'''

new_str = '''    sources = body.get("sources", ["twitter", "news"])
    mode = str(body.get("mode", "demo"))

    try:
        req_id = start_scrape_pipeline(keyword, limit, sources, mode=mode)
        return jsonify({"req_id": req_id, "status": "PENDING"})'''

if old_str in content:
    content = content.replace(old_str, new_str)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced successfully in app.py")
else:
    print("Could not find the target string in app.py")
