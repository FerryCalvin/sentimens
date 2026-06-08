with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_str = '''@app.route("/api/results/precomputed", methods=["GET"])
def api_precomputed():
    import os, pandas as pd
    from utils import get_overall_distribution, get_timeline_data, get_top_items
    file_path = os.path.join("data", "precomputed_large.csv")
    if not os.path.exists(file_path):
        return jsonify({"error": "Pre-computed data not found."}), 404
    df = pd.read_csv(file_path)
    return jsonify({
        "distribution": get_overall_distribution(df),
        "timeline": get_timeline_data(df),
        "top_items": get_top_items(df, n=100)
    })

@app.route("/api/results/<req_id>", methods=["GET"])'''

content = content.replace('@app.route("/api/results/<req_id>", methods=["GET"])', new_str)
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added api_precomputed back.")
