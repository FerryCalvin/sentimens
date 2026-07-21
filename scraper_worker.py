"""
scraper_worker.py — Dijalankan sebagai subprocess terpisah oleh pipeline.py
Menerima args: keyword, limit, source_type
Output: JSON ke stdout
"""
import asyncio
import json
import sys
import os
import logging

logging.basicConfig(level=logging.WARNING)  # Suppress info logs ke stderr

# Tambah path scraper
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scraper"))

from twitter import scrape_twitter
from web_search import scrape_web_search
from threads import scrape_threads


async def run_scrape(keyword: str, limit: int, source_type: str) -> list:
    if source_type == "twitter":
        return await scrape_twitter(keyword, limit)
    if source_type == "threads":
        return await scrape_threads(keyword, limit)
    return await scrape_web_search(keyword, limit)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(json.dumps([]))
        sys.exit(0)

    keyword = sys.argv[1]
    limit = int(sys.argv[2])
    source_type = sys.argv[3]

    try:
        results = asyncio.run(run_scrape(keyword, limit, source_type))
        print(json.dumps(results, ensure_ascii=False))
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        print(json.dumps([]))
