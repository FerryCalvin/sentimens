import asyncio, sys
sys.path.insert(0, 'scraper')
from web_search import scrape_web_search
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

r = asyncio.run(scrape_web_search('IHSG kebakaran prabowo', 20))
print(f'\nTotal: {len(r)} hasil')
for x in r[:8]:
    print(f"  [{x['source']:12}] {x['raw_text'][:90]}")
