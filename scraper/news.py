import urllib.parse
import uuid
import asyncio
from datetime import datetime
from typing import List
import feedparser
from newspaper import Article

async def process_news_item(entry, keyword) -> dict:
    """Helper to process a single news item asynchronously to avoid blocking."""
    # Run newspaper extraction in a thread since newspaper3k is synchronous
    loop = asyncio.get_event_loop()
    
    url = getattr(entry, 'link', '')
    title = getattr(entry, 'title', '')
    description = getattr(entry, 'description', '')
    
    # Get date from RSS
    published_parsed = getattr(entry, 'published_parsed', None)
    if published_parsed:
        date_formatted = datetime(*published_parsed[:6]).strftime("%Y-%m-%d")
    else:
        date_formatted = datetime.now().strftime("%Y-%m-%d")

    raw_text = f"{title}. {description}"
    
    # Try to extract full text using newspaper3k
    if url:
        try:
            article = Article(url, language='id')
            # Run the synchronous download and parse in an executor
            await loop.run_in_executor(None, article.download)
            await loop.run_in_executor(None, article.parse)
            
            if article.text and len(article.text) > len(raw_text):
                # Take up to a certain amount of characters to prevent massive texts
                # or just take the full text if desired.
                raw_text = article.text
        except Exception as e:
            print(f"Failed to extract full text for {url}: {e}")
            
    # Clean up massive text: max 500 characters so it fits well
    if len(raw_text) > 1000:
        raw_text = raw_text[:1000] + "..."

    return {
        "id": str(uuid.uuid4()),
        "source": "news",
        "raw_text": raw_text,
        "date": date_formatted,
        "url": url
    }

async def scrape_news(keyword: str, limit: int) -> List[dict]:
    results = []
    
    # URL encode the keyword
    query = urllib.parse.quote(keyword)
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"
    
    # Run the feed parsing in executor since it's synchronous HTTP request inside feedparser
    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, rss_url)
    
    if not feed or not feed.entries:
        print(f"News scraper: No articles found for '{keyword}'.")
        return results
        
    entries_to_process = feed.entries[:limit]
    
    # Process them concurrently
    tasks = [process_news_item(entry, keyword) for entry in entries_to_process]
    if tasks:
        results = await asyncio.gather(*tasks)
        
    return list(results)
