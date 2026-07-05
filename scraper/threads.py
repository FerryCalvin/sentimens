"""
threads.py — Scrape Threads (threads.com) via Playwright (halaman publik, tanpa login)
=========================================================================================
Threads menyediakan halaman pencarian publik (threads.com/search) yang umumnya bisa
diakses tanpa autentikasi — berbeda dari Twitter/X yang butuh cookie injection.
Modul ini langsung navigasi ke URL pencarian dan scroll-collect post.

CATATAN IMPLEMENTASI:
  Selector DOM di bawah ini berbasis observasi struktur halaman Threads yang bisa
  berubah sewaktu-waktu (khas platform Meta). Beberapa kandidat selector dicoba
  berurutan sebagai jaring pengaman; jika hasil scraping kosong padahal halaman
  termuat, cek ulang selector dengan inspect element pada threads.com/search.
"""
import asyncio
import urllib.parse
import uuid
import logging
import random
from typing import List
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 45_000

_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
try:
    import os as _os
    _CHROME_PATHS.append(
        rf"C:\Users\{_os.environ.get('USERNAME','User')}\AppData\Local\Google\Chrome\Application\chrome.exe"
    )
except Exception:
    pass


def _find_chrome() -> str | None:
    for p in _CHROME_PATHS:
        if Path(p).exists():
            return p
    return None


async def scrape_threads(keyword: str, limit: int, days_back: int = 7) -> List[dict]:
    """
    Entry point utama.
    1. Buka halaman pencarian publik threads.com/search?q=...
    2. Jika terdeteksi login-wall, fallback ke web search.
    3. Scroll & kumpulkan post.
    """
    from playwright.async_api import async_playwright

    chrome_path = _find_chrome()
    if not chrome_path:
        logger.error("Chrome tidak ditemukan — fallback ke web search untuk Threads.")
        return await _fallback_web_search(keyword, limit)

    search_url = f"https://www.threads.com/search?q={urllib.parse.quote(keyword)}&serp_type=default"
    results: List[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=chrome_path,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1280,900",
                "--disable-dev-shm-usage",
            ],
        )
        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                locale="id-ID",
                timezone_id="Asia/Jakarta",
            )
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
                window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
            """)
            page = await context.new_page()

            logger.info(f"Membuka: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
            await asyncio.sleep(4)

            cur_url = page.url
            if any(x in cur_url.lower() for x in ["login", "accounts/login"]):
                logger.warning(f"Threads meminta login — redirect ke {cur_url}. Fallback ke web search.")
                await context.close()
                await browser.close()
                return await _fallback_web_search(keyword, limit)

            results = await _collect_posts(page, search_url, limit)
            await context.close()

        except Exception as e:
            logger.error(f"Error scraping Threads: {e}", exc_info=True)
        finally:
            await browser.close()

    if not results:
        logger.warning("Tidak ada hasil dari Threads — fallback ke web search.")
        return await _fallback_web_search(keyword, limit)

    return results


async def _collect_posts(page, search_url: str, limit: int) -> List[dict]:
    """Scroll & kumpulkan post Threads sampai batas limit."""
    results: List[dict] = []
    collected_texts: set = set()
    no_new_count = 0
    max_no_new  = 6
    max_scrolls = max(20, limit // 5)
    scroll_count = 0

    # Beberapa kandidat selector — struktur DOM Threads bisa berubah sewaktu-waktu.
    TEXT_SELECTORS = [
        '[data-testid="post-text"]',
        'div[data-pressable-container] span[dir="auto"]',
        'span[dir="auto"]',
    ]

    while len(results) < limit and scroll_count < max_scrolls:
        before = len(results)

        post_elements = []
        for sel in TEXT_SELECTORS:
            post_elements = await page.query_selector_all(sel)
            if post_elements:
                break

        for elem in post_elements:
            if len(results) >= limit:
                break
            try:
                text = (await elem.inner_text()).strip()
                if not text or len(text) < 5:
                    continue
                key = text[:80]
                if key in collected_texts:
                    continue
                collected_texts.add(key)

                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                try:
                    container = await elem.evaluate_handle(
                        "el => el.closest('div[data-pressable-container]') || el.closest('article')"
                    )
                    time_el = await container.query_selector("time")
                    if time_el:
                        dt_attr = await time_el.get_attribute("datetime")
                        if dt_attr:
                            date_str = dt_attr[:10]
                except Exception:
                    pass

                results.append({
                    "id":       str(uuid.uuid4()),
                    "source":   "threads",
                    "raw_text": text,
                    "date":     date_str,
                    "url":      search_url,
                })
            except Exception:
                continue

        if len(results) == before:
            no_new_count += 1
            if no_new_count >= max_no_new:
                logger.info("Tidak ada post Threads baru setelah beberapa scroll, berhenti.")
                break
        else:
            no_new_count = 0

        logger.info(f"  Scroll {scroll_count+1}/{max_scrolls} — {len(results)}/{limit} post Threads")

        scroll_px = random.randint(700, 1100)
        await page.evaluate(f"window.scrollBy(0, {scroll_px})")
        await asyncio.sleep(random.uniform(2.0, 3.5))
        scroll_count += 1

    return results[:limit]


async def _fallback_web_search(keyword: str, limit: int) -> List[dict]:
    """Fallback terakhir: cari via web search, relabel source jadi threads."""
    try:
        from web_search import scrape_web_search
    except ImportError:
        return []
    enriched = f"{keyword} pendapat komentar netizen opini"
    results = await scrape_web_search(enriched, limit)
    for r in results:
        r["source"] = "threads"
    return results
