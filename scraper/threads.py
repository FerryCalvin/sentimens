"""
threads.py — Scrape Threads (threads.com) via Playwright, dengan cookie login opsional
=========================================================================================
Dua jalur:
  1. Cookie injection (jika scraper/threads_cookies_config.json terisi) — inject
     sessionid + csrftoken dari sesi Threads yang sudah login, mirip pola
     twitter.py. Ini dibuat karena sesi ANONIM mentok pada paginasi pencarian
     (lihat catatan di bawah); BELUM diverifikasi apakah sesi login benar-benar
     membuka lebih banyak hasil pada endpoint pencarian — perlu diuji langsung
     begitu cookie asli tersedia.
  2. Anonim (fallback, dan jalur default jika tidak ada cookie) — halaman
     pencarian publik threads.com/search, tanpa autentikasi sama sekali.

CATATAN HASIL VERIFIKASI LANGSUNG (bukan asumsi dari riset):
  - Teks post TIDAK diambil dari DOM biasa (class Meta teracak, tidak stabil, dan
    campur dengan noise seperti username/timestamp). Sebagai gantinya, halaman
    menyematkan data hidrasi JSON penuh di dalam beberapa tag
    <script type="application/json" data-sjs>. Setiap objek post punya struktur
    `text_post_app_info.text_fragments.fragments[].plaintext` — ini yang dipakai,
    berlaku sama baik untuk sesi cookie maupun anonim.
  - Untuk sesi ANONIM (tanpa login), respons GraphQL yang disematkan di halaman
    pencarian secara eksplisit menyatakan `"has_next_page":false`,
    `"end_cursor":null`, `"extensions":{"is_final":true}` — dikonfirmasi sama
    untuk keyword niche maupun keyword sangat populer, dengan cookie/CSRF/header
    yang terbukti terkirim benar (HTTP 200, bukan 401/403). Ini keterbatasan
    platform pada level resolver pencarian utk sesi anonim, bukan bug scraper,
    dan TIDAK bisa diatasi lewat scroll/parameter URL tambahan.
  - Menariknya, halaman beranda anonim Threads (`threads.com/?hl=en` — beda dari
    halaman pencarian, tidak bisa difilter keyword) TERBUKTI mendapat
    `has_next_page:true` dengan cursor asli. Jadi resolver GraphQL anonim Threads
    BISA melakukan paginasi sungguhan secara umum — hanya resolver *pencarian*
    yang menutup hasil di sesi anonim. Ini alasan cookie login ditambahkan: untuk
    menguji apakah sesi yang login membuka paginasi yang sama pada pencarian.

  - KONFIRMASI (diuji dengan cookie login asli): BENAR, sesi login membuka
    paginasi pencarian — `page_info` menunjukkan `has_next_page:true` dengan
    `end_cursor` asli (bukan null), berbeda total dari sesi anonim. TAPI data
    tambahan itu TIDAK muncul di HTML halaman/data-sjs saat discroll — data
    tambahan datang lewat respons XHR `POST .../graphql/query` terpisah yang
    baru terpicu saat scroll (payload JSON bersih, field sama:
    `data.data.posts[].text_post_app_info...`). Endpoint `/ajax/bz` yang tadinya
    dicurigai sebagai endpoint paginasi ternyata memang cuma beacon telemetry
    (selalu `payload:null`, di kedua jenis sesi) — bukan sumber data.
    Karena itu `_collect_posts()` di bawah menangkap KEDUA sumber: HTML halaman
    awal (data-sjs) DAN respons `/graphql/query` yang terpicu selama scroll.
    Untuk sesi anonim, listener respons ini tidak menangkap apa pun tambahan
    (karena scroll anonim memang tidak pernah memicu query berisi post baru) —
    jadi aman dipakai bersama untuk kedua jalur tanpa cabang kode terpisah.
"""
import asyncio
import json
import random
import re
import urllib.parse
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).parent / "threads_cookies_config.json"
SESSION_FILE = Path(__file__).parent / "threads_session.json"  # dari threads_login.py (manual login)
DEFAULT_TIMEOUT = 45_000

_SJS_SCRIPT_RE = re.compile(
    r'<script type="application/json" data-content-len="\d+" data-sjs="" data-processed="1">(.*?)</script>',
    re.S,
)


def _load_cookies() -> dict:
    """Muat cookies dari threads_cookies_config.json."""
    if COOKIES_FILE.exists():
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Gagal baca threads_cookies_config.json: {e}")
    return {}


def _build_playwright_cookies(raw_cookies: dict) -> list:
    """
    Konversi dict cookies ke format Playwright add_cookies().
    Domain `.threads.com` saja untuk saat ini — jika sesi tidak dikenali saat
    diuji dengan cookie asli, coba tambahkan `.threads.net`/`.instagram.com`
    (belum diverifikasi apakah dibutuhkan).
    """
    cookie_list = []
    for name, value in raw_cookies.items():
        if value:
            cookie_list.append({
                "name":   name,
                "value":  value,
                "domain": ".threads.com",
                "path":   "/",
            })
    return cookie_list


async def scrape_threads(keyword: str, limit: int, days_back: int = 7) -> List[dict]:
    """
    Entry point utama.
    1. Coba inject cookie dari threads_cookies_config.json (jika ada).
    2. Fallback: pakai sesi login manual tersimpan (threads_session.json, dari threads_login.py).
    3. Fallback: scrape anonim tanpa login (halaman publik threads.com/search).
    4. Fallback akhir (di dalam masing-masing jalur): web search.
    """
    if days_back and days_back > 7:
        logger.info(
            f"[Threads] days_back={days_back} diminta, tapi pencarian Threads tidak punya "
            "kapabilitas filter tanggal (selalu recency-biased) — parameter diterima demi "
            "simetri API, tidak berpengaruh. Keterbatasan platform, bukan bug."
        )

    raw_cookies = _load_cookies()

    if raw_cookies.get("sessionid"):
        logger.info("Cookies Threads ditemukan — coba inject sebelum fallback ke akses anonim.")
        results = await _scrape_with_cookies(keyword, limit, raw_cookies)
        if results:
            logger.info(f"Threads (cookie): {len(results)} post")
            return results
        logger.warning("Cookie injection Threads gagal (mungkin expired). Coba sesi login manual...")

    if SESSION_FILE.exists() and SESSION_FILE.stat().st_size > 1000:
        logger.info("Sesi login manual Threads ditemukan — coba pakai sebelum akses anonim.")
        results = await _scrape_with_session(keyword, limit)
        if results:
            logger.info(f"Threads (session): {len(results)} post")
            return results
        logger.warning("Sesi login manual Threads gagal (mungkin expired). Coba akses anonim...")

    logger.info(
        "[Threads] Sesi anonim punya batas keras platform pada resolver pencarian "
        "(has_next_page:false setelah ~20 hasil) — kesabaran scroll tidak bisa menambah "
        "yield di jalur ini. Redistribusi kuota ke Twitter/Web adalah perilaku normal, bukan anomali."
    )
    return await _scrape_anonymous(keyword, limit)


async def _scrape_with_cookies(keyword: str, limit: int, raw_cookies: dict) -> List[dict]:
    """Inject cookie Threads (sessionid, csrftoken, dst) ke context dari browser bersama, lalu scrape."""
    from browser_manager import manager as browser_manager

    playwright_cookies = _build_playwright_cookies(raw_cookies)
    search_url = f"https://www.threads.com/search?q={urllib.parse.quote(keyword)}&serp_type=default"
    results: List[dict] = []

    context = await browser_manager.new_context(
        viewport={"width": 1280, "height": 900},
        locale="id-ID",
        timezone_id="Asia/Jakarta",
    )
    try:
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
        """)

        await context.add_cookies(playwright_cookies)
        logger.info(f"Injected {len(playwright_cookies)} cookies Threads ke browser")

        page = await context.new_page()

        logger.info(f"Membuka (cookie): {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
        await asyncio.sleep(4)

        cur_url = page.url
        if any(x in cur_url.lower() for x in ["login", "accounts/login"]):
            logger.warning(f"Cookie Threads tidak valid — redirect ke {cur_url}")
            return []

        logger.info(f"Cookie Threads valid! URL: {cur_url[:60]}")
        results = await _collect_posts(page, search_url, limit)

    except Exception as e:
        logger.error(f"Error scraping Threads dengan cookies: {e}", exc_info=True)
    finally:
        await context.close()

    return results


async def _scrape_with_session(keyword: str, limit: int) -> List[dict]:
    """Pakai storage_state dari threads_session.json (hasil threads_login.py) untuk context baru, lalu scrape."""
    from browser_manager import manager as browser_manager

    search_url = f"https://www.threads.com/search?q={urllib.parse.quote(keyword)}&serp_type=default"
    results: List[dict] = []

    context = await browser_manager.new_context(
        storage_state=str(SESSION_FILE),
        viewport={"width": 1280, "height": 900},
        locale="id-ID",
        timezone_id="Asia/Jakarta",
    )
    try:
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
        """)

        page = await context.new_page()

        logger.info(f"Membuka (session): {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
        await asyncio.sleep(4)

        cur_url = page.url
        if any(x in cur_url.lower() for x in ["login", "accounts/login"]):
            logger.warning(f"Sesi Threads tidak valid — redirect ke {cur_url}")
            return []

        logger.info(f"Sesi Threads valid! URL: {cur_url[:60]}")
        results = await _collect_posts(page, search_url, limit)

    except Exception as e:
        logger.error(f"Error scraping Threads dengan sesi login: {e}", exc_info=True)
    finally:
        await context.close()

    return results


async def _scrape_anonymous(keyword: str, limit: int) -> List[dict]:
    """
    Scrape tanpa login: halaman publik threads.com/search. Jika terdeteksi
    login-wall, fallback ke web search.
    """
    from browser_manager import manager as browser_manager

    search_url = f"https://www.threads.com/search?q={urllib.parse.quote(keyword)}&serp_type=default"
    results: List[dict] = []
    need_web_fallback = False

    context = await browser_manager.new_context(
        viewport={"width": 1280, "height": 900},
        locale="id-ID",
        timezone_id="Asia/Jakarta",
    )
    try:
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
            need_web_fallback = True
        else:
            results = await _collect_posts(page, search_url, limit)

    except Exception as e:
        logger.error(f"Error scraping Threads: {e}", exc_info=True)
    finally:
        await context.close()

    if need_web_fallback:
        return await _fallback_web_search(keyword, limit)

    if not results:
        logger.warning("Tidak ada hasil dari Threads — fallback ke web search.")
        return await _fallback_web_search(keyword, limit)

    return results


def _walk_posts(obj, posts: dict, search_url: str) -> None:
    """
    Cari objek post secara rekursif via penanda `text_post_app_info`, dedup ke
    dalam `posts` (dict, key = id post). Dipakai untuk mem-parse baik data
    hidrasi HTML awal maupun respons `/graphql/query` yang terpicu saat scroll.
    """
    if isinstance(obj, dict):
        tpi = obj.get("text_post_app_info")
        if isinstance(tpi, dict):
            fragments = (tpi.get("text_fragments") or {}).get("fragments") or []
            text = "".join(f.get("plaintext", "") for f in fragments if f.get("plaintext"))
            if text and len(text.strip()) >= 5:
                user = (obj.get("user") or {}).get("username") or (obj.get("owner") or {}).get("username", "")
                code = obj.get("code") or ""
                taken_at = obj.get("taken_at")
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if isinstance(taken_at, (int, float)):
                    try:
                        date_str = datetime.fromtimestamp(taken_at, tz=timezone.utc).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                key = obj.get("pk") or obj.get("id") or code or text[:80]
                if key not in posts:
                    url = f"https://www.threads.com/@{user}/post/{code}" if user and code else search_url
                    posts[key] = {
                        "id":       str(uuid.uuid4()),
                        "source":   "threads",
                        "raw_text": text.strip(),
                        "date":     date_str,
                        "url":      url,
                        "author":   user,
                    }
        for v in obj.values():
            _walk_posts(v, posts, search_url)
    elif isinstance(obj, list):
        for v in obj:
            _walk_posts(v, posts, search_url)


def _extract_posts_from_html(html: str, search_url: str) -> List[dict]:
    """
    Parse data hidrasi JSON (<script type="application/json" data-sjs>) yang
    disematkan Threads di halaman awal. Dipakai oleh jalur cookie maupun anonim.
    """
    posts: dict[str, dict] = {}
    for match in _SJS_SCRIPT_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
        except Exception:
            continue
        _walk_posts(data, posts, search_url)
    return list(posts.values())


async def _collect_posts(page, search_url: str, limit: int) -> List[dict]:
    """
    Ambil post dari dua sumber sekaligus:
      1. Data hidrasi JSON di HTML halaman awal (data-sjs).
      2. Respons XHR `POST .../graphql/query` yang terpicu saat scroll —
         DIKONFIRMASI via network capture langsung: untuk sesi COOKIE (login),
         scroll benar-benar memicu request baru berisi post tambahan (payload
         JSON bersih, struktur sama: `data.data.posts[].text_post_app_info`).
         Untuk sesi ANONIM, tidak ada request yang pernah membawa post
         tambahan (hanya beacon `/ajax/bz` yang selalu `payload:null`) — jadi
         listener ini otomatis tidak berpengaruh/aman dipakai di kedua jalur.
    """
    posts: dict[str, dict] = {}

    html = await page.content()
    for match in _SJS_SCRIPT_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
        except Exception:
            continue
        _walk_posts(data, posts, search_url)

    async def on_response(resp):
        if "/graphql/query" not in resp.url and "/api/graphql" not in resp.url:
            return
        try:
            body = await resp.text()
        except Exception:
            return
        if "text_post_app_info" not in body:
            return
        try:
            data = json.loads(body)
        except Exception:
            return
        _walk_posts(data, posts, search_url)

    page.on("response", on_response)

    try:
        scroll_count = 0
        no_new_count = 0
        max_scrolls = max(30, limit // 2)
        max_no_new = 14  # login pagination arrives sparsely (1-3 posts, with gaps) — needs patience
        while len(posts) < limit and scroll_count < max_scrolls:
            before = len(posts)
            await page.evaluate("window.scrollBy(0, 900)")
            await asyncio.sleep(random.uniform(2.2, 3.5))
            if len(posts) == before:
                no_new_count += 1
                if no_new_count >= max_no_new:
                    break  # tidak ada tambahan lagi setelah beberapa scroll
            else:
                no_new_count = 0
            scroll_count += 1
    finally:
        page.remove_listener("response", on_response)

    return list(posts.values())[:limit]


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
