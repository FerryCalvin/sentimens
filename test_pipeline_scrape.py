import sys, os, time
sys.path.insert(0, r'd:\SKRIPSI\sentimens')
sys.path.insert(0, r'd:\SKRIPSI\sentimens\scraper')

# Import pipeline functions directly
from pipeline import _scrape_in_process, _update_status, get_status, start_scrape_pipeline, PENDING

print("Testing _scrape_in_process directly...")
results = _scrape_in_process("kecerdasan buatan", 10, ["web"])
print(f"Results: {len(results)}")
for r in results[:3]:
    src = r['source']
    txt = r['raw_text'][:70]
    print(f"  [{src}] {txt}")
