from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import asyncio

from models import ScrapeRequest
from twitter import scrape_twitter
from news import scrape_news

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Starting Sentiments Scraper API...")
    yield
    # Shutdown logic
    print("Shutting down Sentiments Scraper API...")

app = FastAPI(title="Sentiments Scraper API", lifespan=lifespan)

@app.post("/scrape")
async def scrape(payload: ScrapeRequest):
    try:
        tasks = []
        # Calculate limit per source to not exceed overall limit
        num_sources = len(payload.sources)
        if num_sources == 0:
            return {"status": "success", "keyword": payload.keyword, "total_results": 0, "data": []}
            
        limit_per_source = max(1, payload.limit // num_sources)
        
        twitter_task = None
        news_task = None
        
        if "twitter" in payload.sources:
            twitter_task = asyncio.create_task(scrape_twitter(payload.keyword, limit_per_source))
        if "news" in payload.sources:
            news_task = asyncio.create_task(scrape_news(payload.keyword, limit_per_source))
            
        results = []
        if twitter_task:
            twitter_data = await twitter_task
            results.extend(twitter_data)
        if news_task:
            news_data = await news_task
            results.extend(news_data)
            
        return {
            "status": "success", 
            "keyword": payload.keyword, 
            "total_results": len(results), 
            "data": results
        }
    except Exception as e:
        print(f"Scraping error: {e}")
        return {
            "status": "error",
            "message": f"Scraping failed: {str(e)}"
        }

@app.get("/health")
async def health():
    return {"status": "ok", "scrapers": ["twitter", "news"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
