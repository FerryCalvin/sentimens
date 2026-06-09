import asyncio, sys, logging
sys.path.insert(0, 'scraper')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

from twitter import scrape_twitter

r = asyncio.run(scrape_twitter('IHSG kebakaran prabowo', 20))
print(f'\nTotal Twitter: {len(r)} hasil')
for x in r[:5]:
    print(f"  [{x['source']}] {x['raw_text'][:90]}")
