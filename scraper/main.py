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
import logging
import sys
import os
from dotenv import load_dotenv

load_dotenv()
_DEFAULT_LIMIT     = int(os.getenv("SCRAPE_LIMIT", "200"))
_DEFAULT_DAYS_BACK = int(os.getenv("DAYS_BACK",    "7"))

sys.path.insert(0, os.path.dirname(__file__))

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = Flask(__name__)


def run_async(coro):
    """Jalankan coroutine async dari thread synchronous Flask."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _scrape_parallel(keyword: str, twitter_limit: int, web_limit: int, sources: list, days_back: int = 7) -> dict:
    """
    Jalankan Twitter + web search secara PARALEL menggunakan asyncio.gather.

    Twitter adalah sumber utama — mendapat jatah penuh (twitter_limit).
    Web search berjalan bersamaan sebagai enrichment (web_limit).
    """
    from twitter import scrape_twitter
    from web_search import scrape_web_search

    tasks = []
    labels = []

    if "twitter" in sources:
        tasks.append(scrape_twitter(keyword, twitter_limit, days_back=days_back))
        labels.append("twitter")

    if "web" in sources or "news" in sources:
        tasks.append(scrape_web_search(keyword, web_limit, days_back=days_back))
        labels.append("web")

    if not tasks:
        return {"twitter": [], "web": []}

    # Jalankan semua task bersamaan
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    output = {"twitter": [], "web": []}
    for label, result in zip(labels, results_list):
        if isinstance(result, Exception):
            logger.error(f"Error scraping {label}: {result}")
            output[label] = []
        else:
            output[label] = result or []
            logger.info(f"{label}: {len(output[label])} hasil")

    return output


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

    return jsonify({
        "status": "ok",
        "scrapers": ["twitter", "web"],
        "twitter_auth": tw_status,
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
        sources   = data.get("sources", ["twitter", "web"])
        days_back = int(data.get("days_back", _DEFAULT_DAYS_BACK))

        if not keyword:
            return jsonify({"status": "error", "message": "keyword required"}), 400

        limit     = max(10, min(limit, 500))
        days_back = max(1, min(days_back, 30))

        # ── Bagi jatah ─────────────────────────────────────────────────
        # Twitter mendapat 100% dari limit sebagai sumber utama.
        # Web search berjalan paralel dan memberikan enrichment
        # (hasilnya digabung, lalu dipotong ke limit).
        twitter_limit = limit                       # sumber utama: dapat semua
        web_limit     = max(20, limit // 3)         # enrichment: ~1/3 dari limit

        logger.info(
            f"Scraping paralel | keyword='{keyword}' | "
            f"target={limit} | twitter={twitter_limit} | web={web_limit} | days_back={days_back}"
        )

        # Jalankan paralel
        scraped = run_async(_scrape_parallel(keyword, twitter_limit, web_limit, sources, days_back=days_back))

        twitter_results = scraped.get("twitter", [])
        web_results     = scraped.get("web", [])

        # ── Gabungkan: Twitter dulu, web sebagai pelengkap ──────────────
        combined = list(twitter_results)

        # Tambahkan web hanya jika Twitter kurang dari limit
        existing_texts = {r.get("raw_text", "")[:80] for r in combined}
        for item in web_results:
            if len(combined) >= limit:
                break
            key = item.get("raw_text", "")[:80]
            if key and key not in existing_texts:
                existing_texts.add(key)
                combined.append(item)

        logger.info(
            f"Total gabungan: {len(combined)} "
            f"(Twitter: {len(twitter_results)}, Web: {len(web_results)})"
        )

        return jsonify({
            "status":        "success",
            "keyword":       keyword,
            "count":         len(combined),
            "total_results": len(combined),
            "twitter_count": len(twitter_results),
            "web_count":     len(web_results),
            "data":          combined,
        })

    except Exception as e:
        logger.error(f"Scraping error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    print("Starting SentimenS Scraper API on port 8000...")
    print("Twitter + Web berjalan PARALEL untuk hasil maksimal.")
    app.run(host="127.0.0.1", port=8000, debug=False, threaded=True)
