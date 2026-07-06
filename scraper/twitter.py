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
import urllib.parse
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


async def scrape_twitter(keyword: str, limit: int, days_back: int = 7) -> List[dict]:
    """
    Entry point utama.
    1. Coba inject cookie dari cookies_config.json
    2. Fallback: pakai session Playwright lama (twitter_session.json)
    3. Fallback akhir: web search
    """
    twitter_query = keyword
    raw_cookies = _load_cookies()

    if raw_cookies.get("auth_token") or raw_cookies.get("ct0"):
        logger.info("Cookies ditemukan — inject langsung ke browser (tanpa login form).")
        results = await _scrape_with_cookies(twitter_query, limit, raw_cookies, days_back=days_back)
        if results:
            logger.info(f"Twitter (cookie): {len(results)} tweet")
            return results
        logger.warning("Cookie injection gagal (mungkin expired). Coba session lama...")

    # Fallback: session Playwright lama
    if SESSION_FILE.exists() and SESSION_FILE.stat().st_size > 1000:
        logger.info("Mencoba twitter_session.json (session lama)...")
        results = await _scrape_with_session(twitter_query, limit, days_back=days_back)
        if results:
            return results

    logger.warning("Semua auth Twitter gagal. Fallback ke web search.")
    return await _fallback_web_search(keyword, limit)


async def _scrape_one_window(
    search_url: str, limit: int, *, cookies: dict | None = None, storage_state: str | None = None
) -> tuple[List[dict], bool]:
    """
    Buka 1 context (browser bersama dari browser_manager), scrape 1 window
    pencarian (1 rentang tanggal), lalu tutup context (bukan browser).
    Returns (results, auth_failed) — auth_failed=True berarti cookie/session
    tidak valid (redirect ke login), sehingga caller sebaiknya berhenti
    mencoba bucket berikutnya dan fallback ke jalur auth lain.
    """
    from browser_manager import manager as browser_manager

    context_kwargs = {
        "viewport": {"width": 1280, "height": 900},
        "locale": "id-ID",
        "timezone_id": "Asia/Jakarta",
    }
    if storage_state:
        context_kwargs["storage_state"] = storage_state

    context = await browser_manager.new_context(**context_kwargs)
    results: List[dict] = []
    try:
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
        """)

        if cookies:
            playwright_cookies = _build_playwright_cookies(cookies)
            await context.add_cookies(playwright_cookies)
            logger.info(f"Injected {len(playwright_cookies)//2} cookies ke browser")

        page = await context.new_page()

        logger.info(f"Membuka: {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
        await asyncio.sleep(4)

        cur_url = page.url
        if any(x in cur_url.lower() for x in ["login", "i/flow", "signup"]):
            logger.warning(f"Auth tidak valid — redirect ke {cur_url}")
            return [], True

        results = await _collect_tweets(page, search_url, limit)

        # Jika Top tab habis sebelum limit, coba Latest tab (&f=live)
        if len(results) < limit:
            remaining = limit - len(results)
            latest_url = search_url.replace("f=top", "f=live")
            logger.info(
                f"Top tab exhausted ({len(results)}/{limit}) — "
                f"switching to Latest tab for {remaining} more..."
            )
            await page.goto(latest_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
            await asyncio.sleep(3)
            more = await _collect_tweets(page, latest_url, remaining)
            existing_keys = {r["raw_text"][:80] for r in results}
            added = 0
            for r in more:
                key = r["raw_text"][:80]
                if key not in existing_keys:
                    existing_keys.add(key)
                    results.append(r)
                    added += 1
            if added:
                logger.info(f"Latest tab added {added} tweets. Total: {len(results)}")

    except Exception as e:
        logger.error(f"Error scraping window: {e}", exc_info=True)
    finally:
        await context.close()

    return results, False


async def _scrape_windowed(keyword: str, limit: int, days_back: int, *,
                            cookies: dict | None = None, storage_state: str | None = None) -> List[dict]:
    """Bagi `days_back` jadi beberapa bucket tanggal dan scrape tiap bucket via _scrape_one_window."""
    from date_buckets import build_date_buckets

    buckets = build_date_buckets(days_back)
    per_bucket_limit = max(5, limit // len(buckets))
    all_results: List[dict] = []
    seen: set = set()

    for i, (since_date, until_date) in enumerate(buckets):
        if len(all_results) >= limit:
            break
        full_query = f"{keyword} since:{since_date} until:{until_date}"
        search_url = f"https://x.com/search?q={urllib.parse.quote(full_query)}&src=typed_query&f=top"

        window_results, auth_failed = await _scrape_one_window(
            search_url, per_bucket_limit, cookies=cookies, storage_state=storage_state
        )
        if auth_failed:
            logger.warning("Auth invalid pada bucket pertama — menghentikan loop, jalur ini dianggap gagal total.")
            return []

        for r in window_results:
            key = r["raw_text"][:80]
            if key not in seen:
                seen.add(key)
                all_results.append(r)

        if i < len(buckets) - 1:
            await asyncio.sleep(random.uniform(1.5, 3.0))  # jeda antar-bucket, anti-burst

    if len(buckets) > 1:
        logger.info(f"Windowed scrape: {len(buckets)} bucket, {len(all_results)} tweet unik terkumpul")

    return all_results[:limit]


async def _scrape_with_cookies(keyword: str, limit: int, raw_cookies: dict, days_back: int = 7) -> List[dict]:
    """Buka Chrome (browser bersama), inject cookies X, scrape x.com/search per bucket tanggal."""
    return await _scrape_windowed(keyword, limit, days_back, cookies=raw_cookies)


async def _scrape_with_session(keyword: str, limit: int, days_back: int = 7) -> List[dict]:
    """Fallback: pakai Playwright storage_state lama, scrape x.com/search per bucket tanggal."""
    return await _scrape_windowed(keyword, limit, days_back, storage_state=str(SESSION_FILE))


async def _collect_tweets(page, search_url: str, limit: int) -> List[dict]:
    """Scroll & kumpulkan tweet sampai batas limit."""
    results: List[dict] = []
    collected_texts: set = set()
    no_new_count = 0
    max_no_new  = 10
    max_scrolls = max(30, limit // 3)
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
