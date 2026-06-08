from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import asyncio
import logging

from models import ScrapeRequest
from twitter import scrape_twitter
from web_search import scrape_web_search

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Sentiments Scraper API...")
    yield
    print("Shutting down Sentiments Scraper API...")

app = FastAPI(title="Sentiments Scraper API", lifespan=lifespan)


@app.post("/scrape")
async def scrape(payload: ScrapeRequest):
    """
    Endpoint scraping utama.
    Sources yang didukung: 'twitter', 'web'
    """
    try:
        num_sources = len(payload.sources)
        if num_sources == 0:
            return {
                "status": "success",
                "keyword": payload.keyword,
                "total_results": 0,
                "data": []
            }

        limit_per_source = max(1, payload.limit // num_sources)

        tasks = []
        source_labels = []

        if "twitter" in payload.sources:
            tasks.append(asyncio.create_task(
                scrape_twitter(payload.keyword, limit_per_source)
            ))
            source_labels.append("twitter")

        # Dukung "web" dan "news" (keduanya pakai web_search)
        if "web" in payload.sources or "news" in payload.sources:
            tasks.append(asyncio.create_task(
                scrape_web_search(payload.keyword, limit_per_source)
            ))
            source_labels.append("web")

        # Jalankan semua task secara paralel
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for label, task_result in zip(source_labels, task_results):
            if isinstance(task_result, Exception):
                logger.error(f"Error scraping {label}: {task_result}")
                continue
            results.extend(task_result)

        return {
            "status": "success",
            "keyword": payload.keyword,
            "total_results": len(results),
            "data": results
        }

    except Exception as e:
        logger.error(f"Scraping error: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Scraping failed: {str(e)}"
        }


@app.get("/health")
async def health():
    return {"status": "ok", "scrapers": ["twitter", "web"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
