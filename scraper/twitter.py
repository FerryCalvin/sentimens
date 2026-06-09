"""
twitter.py — Scrape X (Twitter) via Playwright + Cookie Injection
==================================================================
Menggunakan pendekatan COOKIE INJECTION (bukan form login):
  1. Baca auth_token + ct0 dari scraper/cookies_config.json
  2. Inject langsung ke Playwright browser context
  3. Langsung buka x.com/search tanpa perlu login form
  4. Scroll & kumpulkan tweet

Keunggulan vs form login:
  - Tidak ada timeout saat membuka halaman login
  - Tidak ada risiko CAPTCHA / 2FA
  - Jauh lebih cepat dan reliable
"""
# ╔══════════════════════════════════════════════════════════════════╗
# ║           !! CARA MEMPERBARUI COOKIE X/TWITTER !!               ║
# ║                                                                  ║
# ║  Jika scraping X selalu redirect ke halaman login, berarti      ║
# ║  cookie di cookies_config.json sudah EXPIRED. Ikuti langkah:   ║
# ║                                                                  ║
# ║  CARA OTOMATIS (direkomendasikan):                               ║
# ║    1. Dari folder sentimens/, jalankan:                          ║
# ║       python export_twitter_cookies.py                           ║
# ║    2. Ikuti instruksi (paste auth_token & ct0)                   ║
# ║                                                                  ║
# ║  CARA MANUAL (via DevTools):                                     ║
# ║    1. Buka https://x.com di Chrome, pastikan sudah login         ║
# ║    2. Tekan F12 → tab "Application"                              ║
# ║    3. Sidebar kiri: Storage → Cookies → https://x.com            ║
# ║    4. Cari baris Name = "auth_token"  → copy seluruh Value       ║
# ║    5. Cari baris Name = "ct0"         → copy seluruh Value       ║
# ║    6. Edit file: scraper/cookies_config.json                     ║
# ║       Isi seperti contoh di bawah, lalu SIMPAN:                  ║
# ║                                                                  ║
# ║    {                                                             ║
# ║        "auth_token": "PASTE_AUTH_TOKEN_DI_SINI",                 ║
# ║        "ct0":        "PASTE_CT0_DI_SINI",                        ║
# ║        "guest_id":   "",                                          ║
# ║        "twid":       "",                                          ║
# ║        "gt":         ""                                           ║
# ║    }                                                             ║
# ║                                                                  ║
# ║  Setelah update, restart scraper: sentiments start               ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio
import json
import uuid
import logging
import random
from typing import List
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).parent / "cookies_config.json"
SESSION_FILE = Path(__file__).parent / "twitter_session.json"  # fallback lama
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


def _load_cookies() -> dict:
    """Muat cookies dari cookies_config.json."""
    if COOKIES_FILE.exists():
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Gagal baca cookies_config.json: {e}")
    return {}


def _build_playwright_cookies(raw_cookies: dict) -> list:
    """Konversi dict cookies ke format Playwright add_cookies()."""
    cookie_list = []
    for name, value in raw_cookies.items():
        if value:  # skip yang kosong
            cookie_list.append({
                "name":   name,
                "value":  value,
                "domain": ".x.com",
                "path":   "/",
            })
            # Tambahkan juga untuk domain .twitter.com (compat)
            cookie_list.append({
                "name":   name,
                "value":  value,
                "domain": ".twitter.com",
                "path":   "/",
            })
    return cookie_list


async def scrape_twitter(keyword: str, limit: int) -> List[dict]:
    """
    Entry point utama.
    1. Coba inject cookie dari cookies_config.json
    2. Fallback: pakai session Playwright lama (twitter_session.json)
    3. Fallback akhir: web search
    """
    raw_cookies = _load_cookies()

    if raw_cookies.get("auth_token") or raw_cookies.get("ct0"):
        logger.info("Cookies ditemukan — inject langsung ke browser (tanpa login form).")
        results = await _scrape_with_cookies(keyword, limit, raw_cookies)
        if results:
            logger.info(f"Twitter (cookie): {len(results)} tweet")
            return results
        logger.warning("Cookie injection gagal (mungkin expired). Coba session lama...")

    # Fallback: session Playwright lama
    if SESSION_FILE.exists() and SESSION_FILE.stat().st_size > 1000:
        logger.info("Mencoba twitter_session.json (session lama)...")
        results = await _scrape_with_session(keyword, limit)
        if results:
            return results

    logger.warning("Semua auth Twitter gagal. Fallback ke web search.")
    return await _fallback_web_search(keyword, limit)


async def _scrape_with_cookies(keyword: str, limit: int, raw_cookies: dict) -> List[dict]:
    """
    Buka Chrome, inject cookies X, lalu scrape x.com/search.
    Tidak perlu buka halaman login sama sekali.
    """
    from playwright.async_api import async_playwright

    chrome_path = _find_chrome()
    if not chrome_path:
        logger.error("Chrome tidak ditemukan.")
        return []

    playwright_cookies = _build_playwright_cookies(raw_cookies)
    encoded_kw = keyword.replace(" ", "%20")
    search_url  = f"https://x.com/search?q={encoded_kw}&src=typed_query&f=live"

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
            # Buat context kosong, lalu inject cookies
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

            # Inject cookies (seperti autoscraper cookienya)
            await context.add_cookies(playwright_cookies)
            logger.info(f"Injected {len(playwright_cookies)//2} cookies ke browser")

            page = await context.new_page()

            # Langsung ke halaman search (tidak perlu halaman login!)
            logger.info(f"Membuka: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
            await asyncio.sleep(4)

            # Cek apakah masih redirect ke login
            cur_url = page.url
            if any(x in cur_url.lower() for x in ["login", "i/flow", "signup"]):
                logger.warning(f"Cookie tidak valid — redirect ke {cur_url}")
                await context.close()
                return []

            logger.info(f"Cookie valid! URL: {cur_url[:60]}")

            # ── Scroll & kumpulkan tweet ──────────────────────────────────
            results = await _collect_tweets(page, search_url, limit)
            await context.close()

        except Exception as e:
            logger.error(f"Error scraping dengan cookies: {e}", exc_info=True)
        finally:
            await browser.close()

    return results


async def _scrape_with_session(keyword: str, limit: int) -> List[dict]:
    """Fallback: pakai Playwright storage_state lama."""
    from playwright.async_api import async_playwright

    chrome_path = _find_chrome()
    if not chrome_path:
        return []

    encoded_kw = keyword.replace(" ", "%20")
    search_url  = f"https://x.com/search?q={encoded_kw}&src=typed_query&f=live"
    results: List[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=chrome_path,
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
                  "--window-size=1280,900"],
        )
        try:
            context = await browser.new_context(
                storage_state=str(SESSION_FILE),
                viewport={"width": 1280, "height": 900},
                locale="id-ID",
                timezone_id="Asia/Jakarta",
            )
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)
            page = await context.new_page()
            await page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
            await asyncio.sleep(4)

            if any(x in page.url.lower() for x in ["login", "flow"]):
                await context.close()
                return []

            results = await _collect_tweets(page, search_url, limit)
            await context.close()
        except Exception as e:
            logger.error(f"Error session lama: {e}")
        finally:
            await browser.close()

    return results


async def _collect_tweets(page, search_url: str, limit: int) -> List[dict]:
    """Scroll & kumpulkan tweet sampai batas limit."""
    results: List[dict] = []
    collected_texts: set = set()
    no_new_count = 0
    max_no_new  = 6
    max_scrolls = max(20, limit // 5)
    scroll_count = 0

    while len(results) < limit and scroll_count < max_scrolls:
        before = len(results)

        tweet_elements = await page.query_selector_all('[data-testid="tweetText"]')
        for elem in tweet_elements:
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

                # Ambil tanggal
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                try:
                    article  = await elem.evaluate_handle("el => el.closest('article')")
                    time_el  = await article.query_selector("time")
                    if time_el:
                        dt_attr = await time_el.get_attribute("datetime")
                        if dt_attr:
                            date_str = dt_attr[:10]
                except Exception:
                    pass

                results.append({
                    "id":       str(uuid.uuid4()),
                    "source":   "twitter",
                    "raw_text": text,
                    "date":     date_str,
                    "url":      search_url,
                })
            except Exception:
                continue

        if len(results) == before:
            no_new_count += 1
            if no_new_count >= max_no_new:
                logger.info("Tidak ada tweet baru setelah beberapa scroll, berhenti.")
                break
        else:
            no_new_count = 0

        logger.info(f"  Scroll {scroll_count+1}/{max_scrolls} — {len(results)}/{limit} tweet")

        # Scroll dengan sedikit variasi (lebih natural)
        scroll_px = random.randint(700, 1100)
        await page.evaluate(f"window.scrollBy(0, {scroll_px})")
        await asyncio.sleep(random.uniform(2.0, 3.5))
        scroll_count += 1

    return results[:limit]


async def _fallback_web_search(keyword: str, limit: int) -> List[dict]:
    """Fallback terakhir: cari via web search."""
    try:
        from web_search import scrape_web_search
    except ImportError:
        return []
    enriched = f"{keyword} pendapat komentar netizen opini"
    results = await scrape_web_search(enriched, limit)
    for r in results:
        r["source"] = "twitter"
    return results
