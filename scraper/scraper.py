# ============================================================
# scraper/scraper.py — Async Scraping Engine
# Mengimplementasikan FR-SC-01 s/d FR-SC-06
# ============================================================
import asyncio
import random
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

# ---- Konstanta ----
DEFAULT_TIMEOUT = 45_000  # 45 detik dalam ms (FR-SC-06)
MIN_DELAY = 0.5            # Minimum delay antar request (FR-SC-05)
MAX_DELAY = 2.5            # Maximum delay antar request (FR-SC-05)

# User-Agent pool untuk anti-bot evasion
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


async def random_delay() -> None:
    """
    FR-SC-05: Implementasi penundaan acak untuk meniru perilaku manusia.
    Delay acak antara 0.5 – 2.5 detik.
    """
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    await asyncio.sleep(delay)


async def get_browser_context(playwright_instance) -> tuple[Browser, BrowserContext]:
    """
    FR-SC-04: Buat browser context dengan konfigurasi anti-bot evasion.
    Memodifikasi header dan flags untuk menyerupai browser asli.
    """
    # FR-SC-04: Custom browser args untuk bypass fingerprinting
    browser_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--window-size=1920,1080",
        "--start-maximized",
        "--disable-extensions",
        "--disable-plugins-discovery",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    browser = await playwright_instance.chromium.launch(
        headless=True,
        args=browser_args,
    )

    # Pilih user agent acak
    user_agent = random.choice(USER_AGENTS)

    context = await browser.new_context(
        user_agent=user_agent,
        viewport={"width": 1920, "height": 1080},
        locale="id-ID",
        timezone_id="Asia/Jakarta",
        extra_http_headers={
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        },
        java_script_enabled=True,
        ignore_https_errors=True,
    )

    # Override navigator.webdriver untuk bypass deteksi bot
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['id-ID', 'id', 'en-US', 'en']
        });
        window.chrome = { runtime: {} };
    """)

    return browser, context


async def scrape_twitter(keyword: str, limit: int = 100) -> list[dict]:
    """
    Scrape tweet dari X (Twitter) berdasarkan kata kunci.

    Args:
        keyword: Kata kunci pencarian
        limit: Jumlah tweet yang ditargetkan

    Returns:
        List dict dengan key 'text' dan 'date'
    """
    results = []
    search_url = f"https://twitter.com/search?q={keyword.replace(' ', '+')}&src=typed_query&f=live"
    nitter_urls = [
        f"https://nitter.net/search?q={keyword.replace(' ', '+')}&f=tweets",
        f"https://nitter.privacydev.net/search?q={keyword.replace(' ', '+')}&f=tweets",
    ]

    async with async_playwright() as p:
        browser, context = await get_browser_context(p)
        page = await context.new_page()

        try:
            # Coba scraping dari Nitter terlebih dahulu (lebih mudah)
            for nitter_url in nitter_urls:
                try:
                    logger.info(f"Mencoba Nitter: {nitter_url}")
                    await page.goto(nitter_url, timeout=DEFAULT_TIMEOUT, wait_until="networkidle")
                    await random_delay()

                    # Ambil tweet dari Nitter
                    tweets_data = await _extract_nitter_tweets(page, limit)
                    if tweets_data:
                        results.extend(tweets_data)
                        logger.info(f"Berhasil mengambil {len(tweets_data)} tweet dari Nitter")
                        break

                except PlaywrightTimeout:
                    logger.warning(f"Timeout saat mengakses: {nitter_url}")
                    continue
                except Exception as e:
                    logger.warning(f"Error saat scraping Nitter: {e}")
                    continue

            # Jika Nitter gagal, coba Twitter langsung
            if not results:
                logger.info("Nitter gagal, mencoba Twitter langsung...")
                results = await _scrape_twitter_direct(page, keyword, limit)

        finally:
            await context.close()
            await browser.close()

    return results[:limit]


async def _extract_nitter_tweets(page: Page, limit: int) -> list[dict]:
    """Ekstrak tweet dari halaman Nitter."""
    results = []
    
    try:
        # Scroll untuk memuat lebih banyak tweet
        for _ in range(min(5, limit // 20 + 1)):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)
        
        # Ekstrak konten tweet
        tweet_elements = await page.query_selector_all(".timeline-item:not(.show-more)")
        
        for elem in tweet_elements[:limit]:
            try:
                # Ambil teks tweet
                tweet_content = await elem.query_selector(".tweet-content")
                if not tweet_content:
                    continue
                
                text = await tweet_content.inner_text()
                text = text.strip()
                if not text or len(text) < 5:
                    continue
                
                # Ambil tanggal
                date_elem = await elem.query_selector(".tweet-date a")
                date_str = ""
                if date_elem:
                    title_attr = await date_elem.get_attribute("title")
                    date_str = _parse_nitter_date(title_attr or "")
                
                results.append({
                    "text": text,
                    "date": date_str or datetime.now(timezone.utc).isoformat()
                })
                
            except Exception:
                continue
    
    except Exception as e:
        logger.error(f"Error ekstraksi Nitter: {e}")
    
    return results


def _parse_nitter_date(date_str: str) -> str:
    """Parse tanggal dari format Nitter ke ISO 8601."""
    try:
        # Format Nitter: "Jun 5, 2024 · 10:30 AM UTC"
        date_str = re.sub(r" · ", " ", date_str)
        date_str = re.sub(r" UTC$", "", date_str)
        dt = datetime.strptime(date_str, "%b %d, %Y %I:%M %p")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


async def _scrape_twitter_direct(page: Page, keyword: str, limit: int) -> list[dict]:
    """
    Fallback: Scraping langsung dari Twitter.com menggunakan Playwright.
    """
    results = []
    search_url = f"https://twitter.com/search?q={keyword.replace(' ', '%20')}&src=typed_query&f=live"
    
    try:
        await page.goto(search_url, timeout=DEFAULT_TIMEOUT, wait_until="domcontentloaded")
        await asyncio.sleep(3)  # Tunggu konten dimuat
        
        # Scroll untuk memuat lebih banyak tweet
        scroll_count = min(10, limit // 10 + 2)
        for _ in range(scroll_count):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await random_delay()
        
        # Coba berbagai selector untuk tweet
        tweet_selectors = [
            '[data-testid="tweetText"]',
            'article[data-testid="tweet"] div[lang]',
            '[data-testid="tweet"] p',
        ]
        
        for selector in tweet_selectors:
            tweet_elements = await page.query_selector_all(selector)
            if tweet_elements:
                for elem in tweet_elements[:limit]:
                    try:
                        text = await elem.inner_text()
                        text = text.strip()
                        if text and len(text) > 5:
                            results.append({
                                "text": text,
                                "date": datetime.now(timezone.utc).isoformat()
                            })
                    except Exception:
                        continue
                break
    
    except Exception as e:
        logger.error(f"Error scraping Twitter langsung: {e}")
    
    return results


async def scrape_general_web(keyword: str, limit: int = 100) -> list[dict]:
    """
    Scrape konten terkait topik dari berbagai sumber web.
    Mencari berita, forum, dan diskusi online dalam Bahasa Indonesia.

    Args:
        keyword: Kata kunci pencarian
        limit: Jumlah konten yang ditargetkan

    Returns:
        List dict dengan key 'text' dan 'date'
    """
    results = []

    async with async_playwright() as p:
        browser, context = await get_browser_context(p)
        page = await context.new_page()

        try:
            # Sumber 1: Google News / Web Indonesia
            google_results = await _scrape_google_news(page, keyword, min(limit // 2, 30))
            results.extend(google_results)
            
            # Sumber 2: Forum / Kaskus / Reddit Indonesia
            if len(results) < limit:
                forum_results = await _scrape_discussion_forums(page, keyword, limit - len(results))
                results.extend(forum_results)

        finally:
            await context.close()
            await browser.close()

    return results[:limit]


async def _scrape_google_news(page: Page, keyword: str, limit: int) -> list[dict]:
    """Scrape snippet dari Google News/Search."""
    results = []
    
    try:
        # Gunakan Google search untuk berita Indonesia
        search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}&tbm=nws&hl=id&gl=id"
        await page.goto(search_url, timeout=DEFAULT_TIMEOUT, wait_until="domcontentloaded")
        await random_delay()
        
        # Ambil snippet berita
        snippets = await page.query_selector_all(".VwiC3b, .s3v9rd, .MFzkN")
        
        for snippet in snippets[:limit]:
            try:
                text = await snippet.inner_text()
                text = text.strip()
                if text and len(text) > 20:
                    results.append({
                        "text": text,
                        "date": datetime.now(timezone.utc).isoformat(),
                        "source": "Google News"
                    })
            except Exception:
                continue
        
        # Jika snippet kosong, coba ambil dari hasil search biasa
        if not results:
            search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}&hl=id&gl=id"
            await page.goto(search_url, timeout=DEFAULT_TIMEOUT, wait_until="domcontentloaded")
            await random_delay()
            
            # Ambil deskripsi hasil pencarian
            descriptions = await page.query_selector_all(".VwiC3b, .yDYNvb, .lEBKkf")
            for desc in descriptions[:limit]:
                try:
                    text = await desc.inner_text()
                    text = text.strip()
                    if text and len(text) > 20:
                        results.append({
                            "text": text,
                            "date": datetime.now(timezone.utc).isoformat(),
                            "source": "Web Search"
                        })
                except Exception:
                    continue
        
    except Exception as e:
        logger.warning(f"Error scraping Google News: {e}")
    
    return results


async def _scrape_discussion_forums(page: Page, keyword: str, limit: int) -> list[dict]:
    """Scrape diskusi dari forum/komunitas Indonesia."""
    results = []
    
    # Coba berbagai forum Indonesia
    forum_urls = [
        f"https://www.reddit.com/r/indonesia/search/?q={keyword.replace(' ', '+')}",
        f"https://id.quora.com/search?q={keyword.replace(' ', '+')}",
    ]
    
    for url in forum_urls:
        if len(results) >= limit:
            break
        
        try:
            await page.goto(url, timeout=DEFAULT_TIMEOUT, wait_until="domcontentloaded")
            await random_delay()
            
            # Reddit Indonesia
            if "reddit.com" in url:
                posts = await page.query_selector_all('[data-testid="post-container"] h3')
                for post in posts[:limit // 2]:
                    try:
                        text = await post.inner_text()
                        if text and len(text) > 10:
                            results.append({
                                "text": text,
                                "date": datetime.now(timezone.utc).isoformat(),
                                "source": "Reddit"
                            })
                    except Exception:
                        continue
        
        except Exception as e:
            logger.warning(f"Error scraping {url}: {e}")
            continue
    
    return results


async def run_scrape(keyword: str, limit: int = 100) -> dict:
    """
    Fungsi utama scraping yang dipanggil dari FastAPI endpoint.
    Menggabungkan scraping dari berbagai sumber.

    Returns:
        dict: {"status": "success", "count": int, "data": list}
    """
    logger.info(f"Memulai scraping: keyword='{keyword}', limit={limit}")
    
    results = []
    
    try:
        # Coba scraping Twitter/X terlebih dahulu
        twitter_results = await scrape_twitter(keyword, limit)
        results.extend(twitter_results)
        logger.info(f"Twitter: {len(twitter_results)} hasil")
        
        # Jika kurang dari limit, tambah dari sumber web lain
        if len(results) < limit:
            remaining = limit - len(results)
            web_results = await scrape_general_web(keyword, remaining)
            results.extend(web_results)
            logger.info(f"Web umum: {len(web_results)} hasil tambahan")
        
        # Deduplikasi berdasarkan teks
        seen_texts = set()
        unique_results = []
        for r in results:
            text_key = r.get("text", "")[:100]
            if text_key not in seen_texts and text_key:
                seen_texts.add(text_key)
                unique_results.append(r)
        
        results = unique_results[:limit]
        
        logger.info(f"Total hasil unik: {len(results)}")
        
        return {
            "status": "success",
            "count": len(results),
            "data": results,
        }
        
    except Exception as e:
        logger.error(f"Error fatal saat scraping: {e}", exc_info=True)
        return {
            "status": "error",
            "count": 0,
            "data": [],
            "message": "Terjadi kesalahan pada layanan scraping.",
        }
