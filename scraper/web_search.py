"""
web_search.py — Scrape hasil pencarian internet (Google Search) menggunakan Playwright.
Mengambil snippet/deskripsi dari hasil pencarian web umum, bukan hanya berita.
"""
import asyncio
import uuid
import logging
import urllib.parse
from typing import List
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30_000  # 30 detik

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

import random


async def _get_google_snippets(page, keyword: str, limit: int) -> List[dict]:
    """Ambil snippet dari Google Search biasa (web search, bukan news)."""
    results = []
    query = urllib.parse.quote(keyword)

    # Google Web Search (bukan news)
    search_url = f"https://www.google.com/search?q={query}&hl=id&gl=ID&num=20"

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
        await asyncio.sleep(2)

        # Cek apakah ada captcha
        page_content = await page.content()
        if "unusual traffic" in page_content.lower() or "captcha" in page_content.lower():
            logger.warning("Google menampilkan captcha, mencoba Bing...")
            return await _get_bing_snippets(page, keyword, limit)

        # Selector untuk deskripsi/snippet hasil pencarian Google
        snippet_selectors = [
            "div.VwiC3b",          # Snippet utama Google
            "div.yDYNvb",          # Deskripsi alternatif
            "div.lEBKkf",          # Format lain
            "span.aCOpRe",         # Snippet inline
            "div[data-sncf='1']",  # Format terbaru
            "div.r025kc",          # Hasil AMP
            "div.s3v9rd",          # Format lama
        ]

        for selector in snippet_selectors:
            elements = await page.query_selector_all(selector)
            for elem in elements:
                if len(results) >= limit:
                    break
                try:
                    text = await elem.inner_text()
                    text = text.strip()
                    if text and len(text) > 30:
                        results.append({
                            "id": str(uuid.uuid4()),
                            "source": "web_search",
                            "raw_text": text,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "url": search_url,
                        })
                except Exception:
                    continue

            if results:
                break

        # Juga ambil judul hasil pencarian
        if len(results) < limit:
            title_elems = await page.query_selector_all("h3.LC20lb, h3")
            for elem in title_elems[:limit - len(results)]:
                try:
                    text = await elem.inner_text()
                    text = text.strip()
                    if text and len(text) > 10 and text not in [r["raw_text"] for r in results]:
                        results.append({
                            "id": str(uuid.uuid4()),
                            "source": "web_search",
                            "raw_text": text,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "url": search_url,
                        })
                except Exception:
                    continue

    except Exception as e:
        logger.warning(f"Error Google search: {e}")

    return results


async def _get_bing_snippets(page, keyword: str, limit: int) -> List[dict]:
    """Fallback: Ambil snippet dari Bing Search."""
    results = []
    query = urllib.parse.quote(keyword)
    search_url = f"https://www.bing.com/search?q={query}&setlang=id&cc=ID"

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
        await asyncio.sleep(2)

        # Selector snippet Bing
        snippet_selectors = [
            "p.b_algoSlug",
            "div.b_caption p",
            "p.b_lineclamp2",
            "p.b_lineclamp4",
        ]

        for selector in snippet_selectors:
            elements = await page.query_selector_all(selector)
            for elem in elements:
                if len(results) >= limit:
                    break
                try:
                    text = await elem.inner_text()
                    text = text.strip()
                    if text and len(text) > 30:
                        results.append({
                            "id": str(uuid.uuid4()),
                            "source": "web_search",
                            "raw_text": text,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "url": search_url,
                        })
                except Exception:
                    continue

            if results:
                break

    except Exception as e:
        logger.warning(f"Error Bing search: {e}")

    return results


async def _get_duckduckgo_snippets(page, keyword: str, limit: int) -> List[dict]:
    """Fallback kedua: DuckDuckGo."""
    results = []
    query = urllib.parse.quote(keyword)
    search_url = f"https://html.duckduckgo.com/html/?q={query}&kl=id-id"

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
        await asyncio.sleep(2)

        elements = await page.query_selector_all("a.result__snippet, .result__snippet")
        for elem in elements[:limit]:
            try:
                text = await elem.inner_text()
                text = text.strip()
                if text and len(text) > 20:
                    results.append({
                        "id": str(uuid.uuid4()),
                        "source": "web_search",
                        "raw_text": text,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "url": search_url,
                    })
            except Exception:
                continue

    except Exception as e:
        logger.warning(f"Error DuckDuckGo search: {e}")

    return results


async def scrape_web_search(keyword: str, limit: int) -> List[dict]:
    """
    Scrape hasil pencarian internet menggunakan Playwright.
    Mencoba Google → Bing → DuckDuckGo secara berurutan.

    Args:
        keyword: Kata kunci pencarian
        limit: Jumlah hasil yang diinginkan

    Returns:
        List dict dengan key: id, source, raw_text, date, url
    """
    results = []
    user_agent = random.choice(USER_AGENTS)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1280,800",
            ]
        )
        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=user_agent,
                locale="id-ID",
                timezone_id="Asia/Jakarta",
                extra_http_headers={
                    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
            )

            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)

            page = await context.new_page()

            # Coba Google Search
            logger.info(f"Mencari di Google: {keyword}")
            google_results = await _get_google_snippets(page, keyword, limit)
            results.extend(google_results)
            logger.info(f"Google: {len(google_results)} hasil")

            # Jika Google kurang, coba Bing
            if len(results) < limit // 2:
                remaining = limit - len(results)
                logger.info(f"Mencari di Bing: {keyword}")
                bing_results = await _get_bing_snippets(page, keyword, remaining)
                results.extend(bing_results)
                logger.info(f"Bing: {len(bing_results)} hasil")

            # Jika masih kurang, coba DuckDuckGo
            if len(results) < limit // 3:
                remaining = limit - len(results)
                logger.info(f"Mencari di DuckDuckGo: {keyword}")
                ddg_results = await _get_duckduckgo_snippets(page, keyword, remaining)
                results.extend(ddg_results)
                logger.info(f"DuckDuckGo: {len(ddg_results)} hasil")

        except Exception as e:
            logger.error(f"Error web search scraping: {e}", exc_info=True)
        finally:
            await browser.close()

    # Deduplikasi
    seen = set()
    unique_results = []
    for r in results:
        key = r["raw_text"][:100]
        if key not in seen:
            seen.add(key)
            unique_results.append(r)

    logger.info(f"Web search total unik: {len(unique_results)} hasil")
    return unique_results[:limit]
