import asyncio
import uuid
from typing import List
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

async def scrape_twitter(keyword: str, limit: int) -> List[dict]:
    results = []
    
    # URL encode the keyword
    import urllib.parse
    query = urllib.parse.quote(keyword)
    url = f"https://x.com/search?q={query}&src=typed_query&f=live"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Navigate to the search page
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for tweets to load or for a login wall
            try:
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
            except PlaywrightTimeoutError:
                # If no tweets loaded, it might be due to a login wall or no results
                print(f"Twitter scraper: No tweets found for '{keyword}' or hit login wall.")
                return results

            seen_tweets = set()
            scroll_attempts = 0
            max_scroll_attempts = 15

            while len(results) < limit and scroll_attempts < max_scroll_attempts:
                # Get all tweet elements currently on page
                tweets = await page.query_selector_all('article[data-testid="tweet"]')
                
                for tweet in tweets:
                    if len(results) >= limit:
                        break
                        
                    try:
                        # Extract text
                        text_elem = await tweet.query_selector('div[data-testid="tweetText"]')
                        if not text_elem:
                            continue
                        raw_text = await text_elem.inner_text()
                        
                        # Extract date (from the <time> element)
                        time_elem = await tweet.query_selector('time')
                        if time_elem:
                            date_str = await time_elem.get_attribute('datetime')
                            # Convert to YYYY-MM-DD
                            date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            date_formatted = date_obj.strftime("%Y-%m-%d")
                        else:
                            date_formatted = datetime.now().strftime("%Y-%m-%d")

                        # Extract URL (href of the link containing the time element)
                        link_elem = await tweet.query_selector('a:has(time)')
                        tweet_url = None
                        if link_elem:
                            href = await link_elem.get_attribute('href')
                            if href:
                                tweet_url = f"https://x.com{href}"

                        # Use raw_text as uniqueness check to avoid duplicates from scrolling
                        if raw_text not in seen_tweets:
                            seen_tweets.add(raw_text)
                            results.append({
                                "id": str(uuid.uuid4()),
                                "source": "twitter",
                                "raw_text": raw_text,
                                "date": date_formatted,
                                "url": tweet_url
                            })
                    except Exception as e:
                        print(f"Error parsing tweet: {e}")
                        continue
                
                if len(results) < limit:
                    # Scroll down to load more tweets
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await asyncio.sleep(1.5)  # Wait for network/rendering
                    scroll_attempts += 1

            return results
        finally:
            await browser.close()
