"""
web_search.py — Scrape berita & opini dari internet
=====================================================
Pipeline (semua PARALEL):
  1. Google News RSS  — paling reliable, data XML langsung
  2. Yahoo Search     — tidak butuh JS, selector stabil
  3. Detik Finance    — berita keuangan Indonesia
  4. Kompas           — berita nasional Indonesia
  5. Bing via Playwright — fallback JS-rendered

Tidak ada masalah execution context karena requests dipisah dari Playwright.
"""
import asyncio
import uuid
import logging
import random
import re
import xml.etree.ElementTree as ET
import urllib.parse
import warnings
from typing import List
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# Suppress SSL warnings
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

TIMEOUT = 15


def _h(ua=None) -> dict:
    return {
        "User-Agent": ua or random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }


def _item(text: str, source: str, url: str = "") -> dict:
    return {
        "id":       str(uuid.uuid4()),
        "source":   source,
        "raw_text": text.strip(),
        "date":     datetime.now().strftime("%Y-%m-%d"),
        "url":      url,
    }


def _clean(s: str) -> str:
    if not s:
        return ""
    # Hapus tag HTML
    s = re.sub(r'<[^>]+>', ' ', s)
    # Hapus entitas HTML
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&lt;', '<', s)
    s = re.sub(r'&gt;', '>', s)
    s = re.sub(r'&quot;', '"', s)
    s = re.sub(r'&#\d+;', '', s)
    s = re.sub(r'&\w+;', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


# ─────────────────────────────────────────────────────────────
# 1. Google News RSS (PALING RELIABLE — data XML murni)
# ─────────────────────────────────────────────────────────────
def _google_news_rss(keyword: str, limit: int, days_back: int = 7) -> List[dict]:
    """Google News RSS feed — tidak perlu scraping, murni XML."""
    results = []
    query      = urllib.parse.quote_plus(keyword)
    after_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    url = f"https://news.google.com/rss/search?q={query}+after:{after_date}&hl=id&gl=ID&ceid=ID:id"

    try:
        r = requests.get(url, headers=_h(), timeout=TIMEOUT, verify=False)
        root = ET.fromstring(r.content)

        for item in root.findall(".//item"):
            if len(results) >= limit:
                break

            title = _clean(item.findtext("title", ""))
            desc  = _clean(item.findtext("description", ""))
            link  = item.findtext("link", url)

            text = f"{title}. {desc}".strip(". ") if desc and desc != title else title
            if len(text) < 10:
                continue

            # Parse real publication date from RSS instead of using datetime.now()
            date_str = datetime.now().strftime("%Y-%m-%d")
            pub_date_el = item.find("pubDate")
            if pub_date_el is not None and pub_date_el.text:
                try:
                    pub_dt   = parsedate_to_datetime(pub_date_el.text)
                    date_str = pub_dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

            results.append({
                "id":       str(uuid.uuid4()),
                "source":   "google_news",
                "raw_text": text.strip(),
                "date":     date_str,
                "url":      link,
            })

    except Exception as e:
        logger.warning(f"Google News RSS: {e}")

    return results


# ─────────────────────────────────────────────────────────────
# 2. Yahoo Search (tidak butuh JS, bisa di-parse dengan BS4)
# ─────────────────────────────────────────────────────────────
def _yahoo(keyword: str, limit: int) -> List[dict]:
    """Yahoo Search — lebih toleran dari Bing/Google terhadap bot."""
    results = []
    query = urllib.parse.quote_plus(keyword)
    existing = set()

    for start in [1, 11]:   # 2 halaman
        if len(results) >= limit:
            break
        url = f"https://search.yahoo.com/search?p={query}&n=20&b={start}&ei=UTF-8"
        try:
            r = requests.get(url, headers=_h(), timeout=TIMEOUT, verify=False,
                             allow_redirects=True)
            soup = BeautifulSoup(r.text, "lxml")

            for res in soup.select("div.Sr, div.algo, div[class*='algo'], div.s-bd"):
                if len(results) >= limit:
                    break
                try:
                    title_el   = res.select_one("h3 a, h3, .title a")
                    snippet_el = res.select_one("p, .s-snippet, .compText")

                    title   = _clean(title_el.get_text())   if title_el   else ""
                    snippet = _clean(snippet_el.get_text()) if snippet_el else ""
                    link    = title_el["href"] if title_el and title_el.get("href") else url

                    text = f"{title}. {snippet}".strip(". ") if snippet else title
                    if len(text) < 10 or text in existing:
                        continue
                    existing.add(text)
                    results.append(_item(text, "yahoo", link))
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Yahoo: {e}")

    return results


# ─────────────────────────────────────────────────────────────
# 3. Detik Finance + Detik News
# ─────────────────────────────────────────────────────────────
def _detik(keyword: str, limit: int) -> List[dict]:
    """Detik Finance + Detik News search."""
    results = []
    query = urllib.parse.quote_plus(keyword)
    existing = set()

    sources = [
        # Detik Finance search
        f"https://finance.detik.com/search?q={query}",
        # Detik News search
        f"https://news.detik.com/search?q={query}",
        # Detik aggregate search
        f"https://www.detik.com/search/searchall?query={query}",
    ]

    for url in sources:
        if len(results) >= limit:
            break
        try:
            r = requests.get(url, headers=_h(), timeout=TIMEOUT, verify=False)
            soup = BeautifulSoup(r.text, "lxml")

            # Berbagai selector Detik
            items = soup.select(
                "article, .list-content__item, .article__list-item, "
                ".media__row, .box-search__result, .media--"
            )
            if not items:
                # Fallback: ambil semua heading
                items = soup.select("h2, h3")

            for el in items:
                if len(results) >= limit:
                    break
                try:
                    # Coba ambil judul
                    h = el if el.name in ["h2", "h3"] else el.select_one("h2, h3, .title, .media__title")
                    if not h:
                        continue
                    title = _clean(h.get_text())
                    if len(title) < 10 or title in existing:
                        continue

                    # Snippet opsional
                    s = el.select_one("p, .media__desc, .excerpt")
                    snippet = _clean(s.get_text()) if s else ""

                    # Link
                    a = el.select_one("a") or (el if el.name == "a" else None)
                    link = a["href"] if a and a.get("href") else url

                    text = f"{title}. {snippet}".strip(". ") if snippet else title
                    existing.add(text)
                    results.append(_item(text, "detik", link))
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Detik {url[:40]}: {e}")

    return results


# ─────────────────────────────────────────────────────────────
# 4. Kompas
# ─────────────────────────────────────────────────────────────
def _kompas(keyword: str, limit: int) -> List[dict]:
    """Kompas.com search."""
    results = []
    query = urllib.parse.quote_plus(keyword)
    url = f"https://search.kompas.com/search/?q={query}&submit=Submit"
    existing = set()

    try:
        r = requests.get(url, headers=_h(), timeout=TIMEOUT, verify=False)
        soup = BeautifulSoup(r.text, "lxml")

        for art in soup.select(".articleItem, article, .gsc-result, .gs-result"):
            if len(results) >= limit:
                break
            try:
                h = art.select_one("h2, h3, .gsc-title, .articleTitle")
                if not h:
                    continue
                title = _clean(h.get_text())
                if len(title) < 10 or title in existing:
                    continue

                s = art.select_one("p, .gsc-description, .articleDesc")
                snippet = _clean(s.get_text()) if s else ""

                a = art.select_one("a")
                link = a["href"] if a and a.get("href") else url

                text = f"{title}. {snippet}".strip(". ") if snippet else title
                existing.add(text)
                results.append(_item(text, "kompas", link))
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Kompas: {e}")

    return results


# ─────────────────────────────────────────────────────────────
# 5. Bing via Playwright (JS-rendered, sebagai fallback)
# ─────────────────────────────────────────────────────────────
async def _bing_playwright(keyword: str, limit: int) -> List[dict]:
    """Bing via Playwright — untuk konten yang butuh JavaScript."""
    from playwright.async_api import async_playwright

    results = []
    query = urllib.parse.quote_plus(keyword)
    url   = f"https://www.bing.com/search?q={query}&setlang=id&cc=ID&count=30"
    existing = set()

    _CHROME_PATHS = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    chrome_path = next((p for p in _CHROME_PATHS if __import__("pathlib").Path(p).exists()), None)
    if not chrome_path:
        return []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=chrome_path,
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        try:
            ctx  = await browser.new_context(locale="id-ID")
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=25_000)
            await asyncio.sleep(3)

            # Coba berbagai selector Bing
            for sel in ["li.b_algo", "#b_results > li", "ol#b_results li"]:
                items = await page.query_selector_all(sel)
                for el in items:
                    if len(results) >= limit:
                        break
                    try:
                        text = (await el.inner_text()).strip()
                        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 20]
                        for line in lines[:2]:
                            if line not in existing:
                                existing.add(line)
                                results.append(_item(line, "bing", url))
                    except Exception:
                        continue
                if results:
                    break

            await ctx.close()
        except Exception as e:
            logger.warning(f"Bing Playwright: {e}")
        finally:
            await browser.close()

    return results


# ─────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────
async def scrape_web_search(keyword: str, limit: int, days_back: int = 7) -> List[dict]:
    """
    Scrape hasil pencarian dari berbagai sumber secara PARALEL.
    Sumber: Google News RSS + Yahoo + Detik + Kompas + Bing (Playwright)
    """
    logger.info(f"Web search: '{keyword}' | target={limit} | days_back={days_back}")
    per_src = max(15, limit // 2)

    # Jalankan sumber requests secara paralel di thread pool
    all_results: List[dict] = []

    loop = asyncio.get_event_loop()

    def _run_sync_scrapers() -> List[dict]:
        results: List[dict] = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(_google_news_rss, keyword, per_src, days_back): "google_news",
                executor.submit(_yahoo,           keyword, per_src): "yahoo",
                executor.submit(_detik,           keyword, per_src): "detik",
                executor.submit(_kompas,          keyword, per_src): "kompas",
            }
            for future in as_completed(futures, timeout=35):
                src = futures[future]
                try:
                    res = future.result()
                    logger.info(f"  {src}: {len(res)} hasil")
                    results.extend(res)
                except Exception as e:
                    logger.warning(f"  {src} error: {e}")
        return results

    # Run blocking I/O in a thread so the event loop stays free
    sync_results = await loop.run_in_executor(None, _run_sync_scrapers)
    all_results.extend(sync_results)

    # Playwright Bing sebagai tambahan jika masih kurang
    if len(all_results) < limit:
        try:
            bing_results = await _bing_playwright(keyword, limit - len(all_results))
            logger.info(f"  bing_playwright: {len(bing_results)} hasil")
            all_results.extend(bing_results)
        except Exception as e:
            logger.warning(f"  bing_playwright error: {e}")

    # Deduplikasi
    seen = set()
    unique = []
    for r in all_results:
        key = r["raw_text"][:100].lower()
        if key not in seen and len(r["raw_text"]) > 10:
            seen.add(key)
            unique.append(r)

    logger.info(f"Web search selesai: {len(unique)} hasil unik dari {len(all_results)} total")
    return unique[:limit]
