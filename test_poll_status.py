import urllib.request, json, time

BASE = "http://127.0.0.1:5000"
req_id = "e37ec521-31c9-42b5-9ae6-82dcf3ec11af"

print(f"Polling status for {req_id[:8]}...")
status = "PENDING"
for i in range(40):
    time.sleep(3)
    with urllib.request.urlopen(f"{BASE}/api/status/{req_id}", timeout=5) as r:
        d = json.loads(r.read())
    status = d.get("status", "?")
    msg = d.get("message", "")
    prog = d.get("progress", 0)
    print(f"  [{i+1:02d}] {status} {prog}% - {msg[:60]}")
    if status in ("COMPLETED", "FAILED"):
        break

if status == "COMPLETED":
    print(f"\nTotal results: {d.get('total_results')}")
    with urllib.request.urlopen(f"{BASE}/api/results/{req_id}", timeout=10) as r:
        res = json.loads(r.read())
    top = res.get("top_items", [])
    dist = res.get("distribution", {})
    print(f"Distribution: {dist}")
    print(f"Items: {len(top)}")
    for item in top[:5]:
        src = item.get("source", "?")
        lbl = item.get("predicted_label", "?")
        txt = item.get("raw_text", "")[:60]
        print(f"  [{src}][{lbl}] {txt}")
else:
    print(f"\nFailed or timeout. Status: {status}")
