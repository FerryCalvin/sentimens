import asyncio
import httpx
import urllib.parse
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

async def test():
    q = urllib.parse.quote("kecerdasan buatan komentar pendapat")
    url = f"https://www.bing.com/search?q={q}&setlang=id&cc=ID&count=10"
    
    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(url)
        print(f"Status: {resp.status_code}")
        html = resp.text
        print(f"HTML length: {len(html)}")
        print("First 500 chars:")
        print(html[:500])
        print()
        
        # Try different patterns
        patterns = [
            (r'<p class="b_algoSlug[^"]*"[^>]*>(.*?)</p>', "b_algoSlug"),
            (r'<p class="b_paractl[^"]*"[^>]*>(.*?)</p>', "b_paractl"),
            (r'<div class="b_caption">(.*?)</div>', "b_caption"),
        ]
        for pattern, name in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            print(f"Pattern '{name}': {len(matches)} matches")
            for m in matches[:2]:
                clean = re.sub(r'<[^>]+>', '', m).strip()[:80]
                print(f"  -> {clean}")

asyncio.run(test())
