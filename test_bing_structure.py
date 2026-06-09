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
        html = resp.text
        
        # Find all class names that appear in <p> tags
        p_classes = re.findall(r'<p\s+class="([^"]+)"', html)
        print("P tag classes found:")
        for cls in set(p_classes):
            print(f"  .{cls}")
        
        print()
        # Find all class names that appear in <div> tags containing snippet text
        div_classes = re.findall(r'<div\s+class="([^"]+)"', html)
        print("DIV tag classes (first 20 unique):")
        for cls in list(set(div_classes))[:20]:
            print(f"  .{cls}")
        
        # Try to find text paragraphs in results
        print()
        print("Looking for result snippets...")
        # Bing search results usually in li.b_algo
        li_matches = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
        print(f"b_algo items: {len(li_matches)}")
        for item in li_matches[:2]:
            # Extract text
            text = re.sub(r'<[^>]+>', ' ', item)
            text = re.sub(r'\s+', ' ', text).strip()
            print(f"  Text: {text[:150]}")
            print()

asyncio.run(test())
