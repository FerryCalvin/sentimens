"""
main.py — Scraper API (Flask)
==============================
Arsitektur:
  - Twitter/X  : sumber UTAMA  (target: semua limit dari Twitter)
  - Web search : ENRICHMENT    (paralel, mengisi sisa jika Twitter kurang)

Keduanya berjalan BERSAMAAN (concurrent via asyncio.gather),
sehingga web search tidak menunggu Twitter selesai.
"""
from flask import Flask, jsonify, request
import asyncio
import atexit
import logging
import sys
import os
from dotenv import load_dotenv

load_dotenv()
_DEFAULT_LIMIT     = int(os.getenv("SCRAPE_LIMIT", "200"))
_DEFAULT_DAYS_BACK = int(os.getenv("DAYS_BACK",    "365"))
_MAX_DAYS_BACK      = int(os.getenv("MAX_DAYS_BACK", "365"))
_SCRAPE_COROUTINE_TIMEOUT = int(os.getenv("SCRAPE_COROUTINE_TIMEOUT", "1500"))

sys.path.insert(0, os.path.dirname(__file__))

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = Flask(__name__)

from browser_manager import manager as browser_manager


def run_async(coro):
    """Jalankan coroutine async dari thread synchronous Flask (dipakai untuk coroutine yang
    TIDAK menyentuh browser bersama — semua jalur browser-based lewat browser_manager.run_coroutine)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _scrape_parallel(keyword: str, expanded_keyword: str, twitter_limit: int, web_limit: int, threads_limit: int,
                            sources: list, days_back: int = 7, plain_keyword: str | None = None) -> dict:
    """
    Jalankan Twitter + Web search + Threads secara PARALEL menggunakan asyncio.gather.

    Twitter dan Threads adalah sumber utama — masing-masing mendapat jatah penuh.
    Web search berjalan bersamaan sebagai enrichment (web_limit).

    Twitter dan web dapat `expanded_keyword` (hasil LLM query expansion — query
    Boolean bergaya Twitter/X, mis. `("kopi" OR "coffee") jakarta`). Threads dapat
    `plain_keyword` (varian frasa polos hasil expansion yang sama, tanpa operator
    Boolean/tanda kutip) — mesin pencari Threads tidak memahami sintaks Boolean
    tsb dan akan mengembalikan nol hasil jika diberi query Boolean mentah
    (diverifikasi langsung — bukan asumsi), tapi tetap bisa diuntungkan dari
    pengayaan sinonim selama formatnya frasa biasa.
    """
    from twitter import scrape_twitter
    from web_search import scrape_web_search
    from threads import scrape_threads

    plain_keyword = plain_keyword or keyword

    tasks = []
    labels = []

    if "twitter" in sources:
        tasks.append(scrape_twitter(expanded_keyword, twitter_limit, days_back=days_back))
        labels.append("twitter")

    if "web" in sources or "news" in sources:
        tasks.append(scrape_web_search(expanded_keyword, web_limit, days_back=days_back))
        labels.append("web")

    if "threads" in sources:
        tasks.append(scrape_threads(plain_keyword, threads_limit, days_back=days_back))
        labels.append("threads")

    if not tasks:
        return {"twitter": [], "web": [], "threads": []}

    # Jalankan semua task bersamaan
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    output = {"twitter": [], "web": [], "threads": []}
    for label, result in zip(labels, results_list):
        if isinstance(result, Exception):
            logger.error(f"Error scraping {label}: {result}")
            output[label] = []
        else:
            output[label] = result or []
            logger.info(f"{label}: {len(output[label])} hasil")

    return output


async def _scrape_with_redistribution(keyword: str, expanded_keyword: str, plain_keyword: str,
                                       twitter_limit: int, web_limit: int, threads_limit: int,
                                       sources: list, days_back: int = 7) -> dict:
    """
    Jalankan _scrape_parallel, lalu kalau ada sumber yang under-deliver (mis. Threads
    anonim mentok ~20 padahal limit lebih tinggi) dan sumber lain masih longgar,
    jalankan 1 putaran tambahan ke sumber yang longgar dengan bonus kuota.

    CATATAN: ini scroll ulang dari atas (tidak ada cursor yang bisa disambung
    antar call), jadi hasil duplikat di-dedupe — efektifitasnya bergantung pada
    kesabaran scroll yang sudah dinaikkan di twitter.py/threads.py.
    """
    from twitter import scrape_twitter
    from web_search import scrape_web_search
    from threads import scrape_threads

    scraped = await _scrape_parallel(
        keyword, expanded_keyword, twitter_limit, web_limit, threads_limit, sources,
        days_back=days_back, plain_keyword=plain_keyword,
    )

    shortfalls = {}
    if "twitter" in sources:
        shortfalls["twitter"] = max(0, twitter_limit - len(scraped["twitter"]))
    if "threads" in sources:
        shortfalls["threads"] = max(0, threads_limit - len(scraped["threads"]))
    if "web" in sources or "news" in sources:
        shortfalls["web"] = max(0, web_limit - len(scraped["web"]))

    total_shortfall = sum(shortfalls.values())
    headroom = [s for s, short in shortfalls.items() if short == 0]
    if total_shortfall <= 0 or not headroom:
        return scraped

    bonus = max(5, total_shortfall // len(headroom))
    logger.info(f"Redistributing shortfall={total_shortfall} ke {headroom} (+{bonus} tiap sumber)")

    tasks, labels = [], []
    if "twitter" in headroom:
        tasks.append(scrape_twitter(expanded_keyword, bonus, days_back=days_back))
        labels.append("twitter")
    if "web" in headroom:
        tasks.append(scrape_web_search(expanded_keyword, bonus, days_back=days_back))
        labels.append("web")
    if "threads" in headroom:
        tasks.append(scrape_threads(plain_keyword, bonus, days_back=days_back))
        labels.append("threads")

    extra = await asyncio.gather(*tasks, return_exceptions=True)
    for label, res in zip(labels, extra):
        if isinstance(res, Exception):
            logger.warning(f"Redistribution fetch untuk {label} gagal: {res}")
            continue
        existing = {r.get("raw_text", "")[:80] for r in scraped[label]}
        added = 0
        for item in (res or []):
            key = item.get("raw_text", "")[:80]
            if key and key not in existing:
                existing.add(key)
                scraped[label].append(item)
                added += 1
        logger.info(f"Redistribution menambah {added} item {label}")

    return scraped


@app.route("/health", methods=["GET"])
def health():
    from pathlib import Path
    import json
    scraper_dir = Path(__file__).parent

    # Cek cookies_config.json (metode baru — cookie injection)
    cookies_file = scraper_dir / "cookies_config.json"
    cookies_ok = False
    if cookies_file.exists():
        try:
            c = json.loads(cookies_file.read_text())
            cookies_ok = bool(c.get("auth_token") or c.get("ct0"))
        except Exception:
            pass

    # Cek session lama sebagai fallback
    session_exists = (scraper_dir / "twitter_session.json").exists()

    if cookies_ok:
        tw_status = "cookie aktif (inject langsung)"
    elif session_exists:
        tw_status = "session aktif (lama)"
    else:
        tw_status = "tidak ada — jalankan: python export_twitter_cookies.py"

    # Cek threads_cookies_config.json
    threads_cookies_file = scraper_dir / "threads_cookies_config.json"
    threads_cookies_ok = False
    if threads_cookies_file.exists():
        try:
            tc = json.loads(threads_cookies_file.read_text())
            threads_cookies_ok = bool(tc.get("sessionid"))
        except Exception:
            pass

    threads_status = (
        "cookie aktif (inject langsung)" if threads_cookies_ok
        else "tidak ada — akses anonim (batas ~20 hasil/keyword). jalankan: python export_threads_cookies.py"
    )

    return jsonify({
        "status": "ok",
        "scrapers": ["twitter", "web", "threads"],
        "twitter_auth": tw_status,
        "threads_auth": threads_status,
    })


@app.route("/scrape", methods=["POST"])
def scrape():
    """
    Endpoint scraping utama.

    Body JSON:
        keyword  : str   — kata kunci wajib
        limit    : int   — total data target (default 100)
        sources  : list  — ["twitter", "web"] (default keduanya)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON body"}), 400

        keyword   = data.get("keyword", "").strip()
        limit     = int(data.get("limit",     _DEFAULT_LIMIT))
        sources   = data.get("sources", ["twitter", "web", "threads"])
        days_back = int(data.get("days_back", _DEFAULT_DAYS_BACK))

        if not keyword:
            return jsonify({"status": "error", "message": "keyword required"}), 400

        limit     = max(10, min(limit, 500))
        days_back = max(1, min(days_back, _MAX_DAYS_BACK))

        # ── Bagi jatah ─────────────────────────────────────────────────
        # Twitter dan Threads adalah sumber utama, masing-masing dapat 100%
        # dari limit. Web search berjalan paralel sebagai enrichment
        # (hasilnya digabung, lalu dipotong ke limit).
        twitter_limit = limit                       # sumber utama: dapat semua
        threads_limit = limit                       # sumber utama: dapat semua
        web_limit     = max(20, limit // 3)         # enrichment: ~1/3 dari limit

        logger.info(
            f"Scraping paralel | keyword='{keyword}' | "
            f"target={limit} | twitter={twitter_limit} | web={web_limit} | "
            f"threads={threads_limit} | days_back={days_back}"
        )

        # LLM-based query expansion — expands keyword into a Boolean query (Twitter/Web)
        # and a plain merged-phrase variant (Threads, which can't parse Boolean/quotes).
        # Falls back to the original keyword for both on any failure/timeout.
        from query_expansion import expand_query
        expanded_keyword, plain_keyword, expansion_status = expand_query(keyword)

        # Jalankan paralel (di event loop bersama browser_manager) + redistribusi shortfall
        scraped = browser_manager.run_coroutine(
            _scrape_with_redistribution(
                keyword, expanded_keyword, plain_keyword,
                twitter_limit, web_limit, threads_limit, sources, days_back=days_back,
            ),
            timeout=_SCRAPE_COROUTINE_TIMEOUT,
        )

        twitter_results = scraped.get("twitter", [])
        web_results     = scraped.get("web", [])
        threads_results = scraped.get("threads", [])

        # ── Gabungkan proporsional: Twitter, Web, dan Threads adalah sumber
        # PARALEL yang setara (bukan primer + fallback), jadi hasil akhir harus
        # memuat porsi dari ketiganya, bukan salah satu mendominasi lalu
        # memotong yang lain saat displice ke `limit`.
        source_lists = {}
        if "twitter" in sources:
            source_lists["twitter"] = list(twitter_results)
        if "web" in sources or "news" in sources:
            source_lists["web"] = list(web_results)
        if "threads" in sources:
            source_lists["threads"] = list(threads_results)

        n_active = len(source_lists) or 1
        base_quota = limit // n_active
        remainder = limit % n_active

        taken = {}
        leftover = {}
        for i, (src, items) in enumerate(source_lists.items()):
            quota = base_quota + (1 if i < remainder else 0)
            taken[src] = items[:quota]
            leftover[src] = items[quota:]

        shortfall = limit - sum(len(v) for v in taken.values())
        if shortfall > 0:
            for src in source_lists:
                if shortfall <= 0:
                    break
                extra = leftover[src][:shortfall]
                taken[src].extend(extra)
                shortfall -= len(extra)

        # Interleave round-robin supaya hasil akhir benar-benar tercampur
        # (bukan tiga blok berurutan) — penting juga untuk konsumen hilir yang
        # hanya preview N baris pertama (mis. app.py `results[:100]`).
        combined = []
        existing_texts = set()
        max_len = max((len(v) for v in taken.values()), default=0)
        for i in range(max_len):
            for src in source_lists:
                if i < len(taken[src]):
                    item = taken[src][i]
                    key = item.get("raw_text", "")[:80]
                    if key and key in existing_texts:
                        continue
                    if key:
                        existing_texts.add(key)
                    combined.append(item)

        combined = combined[:limit]

        logger.info(
            f"Total gabungan: {len(combined)} "
            f"(Twitter: {len(taken.get('twitter', []))}/{len(twitter_results)}, "
            f"Web: {len(taken.get('web', []))}/{len(web_results)}, "
            f"Threads: {len(taken.get('threads', []))}/{len(threads_results)})"
        )

        return jsonify({
            "status":           "success",
            "keyword":          keyword,
            "expanded_keyword": expanded_keyword,
            "plain_keyword":    plain_keyword,
            "expansion_status": expansion_status,
            "count":         len(combined),
            "total_results": len(combined),
            "twitter_count": len(twitter_results),
            "web_count":     len(web_results),
            "threads_count": len(threads_results),
            "data":          combined,
        })

    except TimeoutError:
        logger.error(
            f"Scraping timeout setelah {_SCRAPE_COROUTINE_TIMEOUT}s — "
            f"kemungkinan besar days_back/limit terlalu besar untuk windowed scraping. "
            f"Coba turunkan days_back atau naikkan SCRAPE_COROUTINE_TIMEOUT."
        )
        return jsonify({
            "status": "error",
            "message": f"Scraping melebihi batas waktu {_SCRAPE_COROUTINE_TIMEOUT}s",
        }), 504

    except Exception as e:
        logger.error(f"Scraping error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    from query_expansion import log_startup_status
    log_startup_status()

    print("Starting SentimenS Scraper API on port 8000...")
    print("Twitter + Web berjalan PARALEL untuk hasil maksimal.")

    # Warm up: launch Chromium sekali sekarang, bukan di request /scrape pertama.
    browser_manager.ensure_started()
    try:
        browser_manager.run_coroutine(browser_manager.get_browser(), timeout=60)
        logger.info("Browser bersama siap (warm start).")
    except Exception as e:
        logger.warning(f"Gagal warm-start browser (akan dicoba lagi saat request pertama): {e}")
    atexit.register(browser_manager.shutdown)

    app.run(host="127.0.0.1", port=8000, debug=False, threaded=True)
