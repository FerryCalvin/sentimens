import asyncio, sys
sys.path.insert(0, r'd:\SKRIPSI\sentimens\scraper')
from twitter import scrape_twitter

async def test():
    results = await scrape_twitter('kecerdasan buatan', 5)
    print(f'Results: {len(results)}')
    for r in results[:3]:
        text = r["raw_text"][:70]
        src = r["source"]
        print(f'  [{src}] {text}')

asyncio.run(test())
