with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
old_str = '# Error Handlers (NFR-S-05)'

new_str = '''@app.route("/api/status/<req_id>", methods=["GET"])
def api_status(req_id):
    from pipeline import get_status
    status_data = get_status(req_id)
    return jsonify(status_data)

@app.route("/api/results/<req_id>", methods=["GET"])
def api_results(req_id):
    from pipeline import get_status
    import json
    status_data = get_status(req_id)
    if status_data.get("status") == "COMPLETED" and status_data.get("file_path"):
        import pandas as pd
        df = pd.read_csv(status_data["file_path"])
        from utils import get_overall_distribution, get_timeline_data, get_top_items
        return jsonify({
            "distribution": get_overall_distribution(df),
            "timeline": get_timeline_data(df),
            "top_items": get_top_items(df, n=100)
        })
    return jsonify({"error": "Results not ready or not found."}), 404

# Error Handlers (NFR-S-05)'''

if old_str in content:
    content = content.replace(old_str, new_str)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Restored api_status and api_results.")
else:
    print("Error Handlers comment not found.")
