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

from web_search import scrape_web_search


async def run_search(keyword: str, limit: int) -> list:
    return await scrape_web_search(keyword, limit)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps([]))
        sys.exit(0)

    keyword = sys.argv[1]
    limit = int(sys.argv[2])

    try:
        results = asyncio.run(run_search(keyword, limit))
        print(json.dumps(results, ensure_ascii=False))
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        print(json.dumps([]))
