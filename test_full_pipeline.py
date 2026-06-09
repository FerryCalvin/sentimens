import urllib.request, json, time

BASE = "http://127.0.0.1:5000"

print("=== FULL E2E TEST ===")

# Start scrape
body = json.dumps({"keyword": "kecerdasan buatan", "limit": 20, "sources": ["twitter", "web"]}).encode()
req = urllib.request.Request(f"{BASE}/api/scrape", data=body, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=10) as r:
    d = json.loads(r.read())

req_id = d["req_id"]
print(f"Job: {req_id[:8]}...")

# Poll
status = "PENDING"
for i in range(50):
    time.sleep(4)
    with urllib.request.urlopen(f"{BASE}/api/status/{req_id}", timeout=5) as r:
        d = json.loads(r.read())
    status = d.get("status", "?")
    prog = d.get("progress", 0)
    msg = d.get("message", "")[:55]
    print(f"  [{i+1:02d}] {status} {prog}% - {msg}")
    if status in ("COMPLETED", "FAILED"):
        break

if status == "COMPLETED":
    total = d.get("total_results", 0)
    print(f"\n✅ SELESAI! {total} data ditemukan")
    with urllib.request.urlopen(f"{BASE}/api/results/{req_id}", timeout=10) as r:
        res = json.loads(r.read())
    print(f"Distribution: {res.get('distribution', {})}")
    for item in res.get("top_items", [])[:5]:
        print(f"  [{item['source']}][{item['predicted_label']}] {item['raw_text'][:60]}")
elif status == "FAILED":
    print(f"\n❌ FAILED: {d.get('message')}")
else:
    print(f"\n⏰ TIMEOUT - last status: {status}")
