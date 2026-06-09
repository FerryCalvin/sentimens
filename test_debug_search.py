import sys, requests, warnings
sys.path.insert(0, 'scraper')
warnings.filterwarnings('ignore')
requests.packages.urllib3.disable_warnings()

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "id-ID,id;q=0.9,en;q=0.7", "Accept": "text/html,*/*"}

from bs4 import BeautifulSoup

# Debug Bing — cari semua class/tag yang ada
print("=== BING SELECTORS DEBUG ===")
r = requests.get("https://www.bing.com/search?q=IHSG+kebakaran+prabowo&setlang=id&count=20", headers=H, timeout=15, verify=False)
soup = BeautifulSoup(r.text, "lxml")

# Cari semua kemungkinan container hasil
for sel in ["li.b_algo", "#b_results li", ".b_algo", "ol#b_results > li", 
            "main li", "#b_content li", ".b_results li"]:
    elems = soup.select(sel)
    if elems:
        print(f"  '{sel}' → {len(elems)} elem | sample: {elems[0].get_text()[:80]}")
    else:
        print(f"  '{sel}' → 0")

# Tampilkan struktur ID utama
ids = [t.get('id') for t in soup.find_all(id=True)][:15]
print(f"IDs ditemukan: {ids}")

print()
print("=== DDG SELECTORS DEBUG ===")
r2 = requests.post("https://html.duckduckgo.com/html/", data={"q":"IHSG kebakaran","kl":"id-id"}, headers=H, timeout=15, verify=False)
soup2 = BeautifulSoup(r2.text, "lxml")

for sel in [".result", ".results_links", ".result__body", "div.links_main",
            ".web-result", "article", ".result__snippet", ".result__title"]:
    elems = soup2.select(sel)
    if elems:
        print(f"  '{sel}' → {len(elems)} elem | sample: {elems[0].get_text()[:80]}")
    else:
        print(f"  '{sel}' → 0")

# Cek body content
body = soup2.find('body')
if body:
    classes = [c for tag in soup2.find_all(class_=True) for c in tag.get('class', []) if 'result' in c.lower()][:10]
    print(f"Classes dengan 'result': {set(classes)}")
