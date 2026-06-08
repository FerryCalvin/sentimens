import asyncio
import uuid
import os
import logging
from typing import List
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Twitter credentials dari environment atau hardcoded
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "@nanashi_dono")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "@Ferrycalvin12345#")

async def _login_twitter(page) -> bool:
    """Login ke Twitter/X dengan akun yang tersedia."""
    try:
        logger.info("Membuka halaman login Twitter...")
        await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Masukkan username/email
        username_input = await page.wait_for_selector(
            'input[autocomplete="username"]', timeout=15000
        )
        await username_input.fill(TWITTER_USERNAME)
        await asyncio.sleep(1)

        # Klik tombol Next
        next_btn = await page.query_selector('div[role="button"]:has-text("Next")')
        if next_btn:
            await next_btn.click()
        else:
            await page.keyboard.press("Enter")
        await asyncio.sleep(2)

        # Cek apakah ada konfirmasi username/phone (kadang Twitter minta ini)
        try:
            unusual_input = await page.wait_for_selector(
                'input[data-testid="ocfEnterTextTextInput"]', timeout=5000
            )
            if unusual_input:
                # Masukkan username tanpa @
                clean_username = TWITTER_USERNAME.lstrip("@")
                await unusual_input.fill(clean_username)
                await asyncio.sleep(1)
                next_btn2 = await page.query_selector('div[role="button"]:has-text("Next")')
                if next_btn2:
                    await next_btn2.click()
                else:
                    await page.keyboard.press("Enter")
                await asyncio.sleep(2)
        except PlaywrightTimeoutError:
            pass  # Tidak ada konfirmasi tambahan, lanjut

        # Masukkan password
        password_input = await page.wait_for_selector(
            'input[name="password"]', timeout=10000
        )
        await password_input.fill(TWITTER_PASSWORD)
        await asyncio.sleep(1)

        # Klik tombol Login
        login_btn = await page.query_selector('div[data-testid="LoginForm_Login_Button"]')
        if login_btn:
            await login_btn.click()
        else:
            await page.keyboard.press("Enter")

        # Tunggu redirect ke home
        await asyncio.sleep(5)

        # Verifikasi login berhasil
        current_url = page.url
        if "home" in current_url or "x.com" in current_url and "login" not in current_url:
            logger.info("Login Twitter berhasil!")
            return True

        # Cek apakah masih di halaman login
        if "login" in current_url or "flow" in current_url:
            logger.warning("Login Twitter mungkin gagal, URL masih di login flow")
            return False

        return True

    except Exception as e:
        logger.error(f"Error saat login Twitter: {e}")
        return False


async def scrape_twitter(keyword: str, limit: int) -> List[dict]:
    """
    Scrape tweet dari X/Twitter dengan auto-login.
    Login menggunakan akun: @nanashi_dono
    """
    results = []

    import urllib.parse
    query = urllib.parse.quote(keyword)
    search_url = f"https://x.com/search?q={query}&src=typed_query&f=live"

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
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                locale="id-ID",
                timezone_id="Asia/Jakarta",
            )

            # Tambah init script untuk bypass bot detection
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)

            page = await context.new_page()

            # Login ke Twitter
            login_ok = await _login_twitter(page)
            if not login_ok:
                logger.warning("Login gagal, mencoba scrape tanpa login...")

            # Navigate ke halaman search
            logger.info(f"Mencari tweet dengan keyword: {keyword}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)

            # Tunggu tweet muncul
            try:
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
            except PlaywrightTimeoutError:
                logger.warning(f"Tidak ada tweet ditemukan untuk keyword: {keyword}")
                return results

            seen_tweets = set()
            scroll_attempts = 0
            max_scroll_attempts = 20
            no_new_count = 0

            while len(results) < limit and scroll_attempts < max_scroll_attempts:
                tweets = await page.query_selector_all('article[data-testid="tweet"]')
                new_found = 0

                for tweet in tweets:
                    if len(results) >= limit:
                        break

                    try:
                        # Ambil teks tweet
                        text_elem = await tweet.query_selector('div[data-testid="tweetText"]')
                        if not text_elem:
                            continue
                        raw_text = await text_elem.inner_text()
                        raw_text = raw_text.strip()

                        if not raw_text or len(raw_text) < 5:
                            continue

                        # Skip jika sudah ada
                        if raw_text in seen_tweets:
                            continue

                        # Ambil tanggal
                        time_elem = await tweet.query_selector("time")
                        if time_elem:
                            date_str = await time_elem.get_attribute("datetime")
                            try:
                                date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                                date_formatted = date_obj.strftime("%Y-%m-%d")
                            except Exception:
                                date_formatted = datetime.now().strftime("%Y-%m-%d")
                        else:
                            date_formatted = datetime.now().strftime("%Y-%m-%d")

                        # Ambil URL tweet
                        link_elem = await tweet.query_selector("a:has(time)")
                        tweet_url = None
                        if link_elem:
                            href = await link_elem.get_attribute("href")
                            if href:
                                tweet_url = f"https://x.com{href}"

                        seen_tweets.add(raw_text)
                        new_found += 1
                        results.append({
                            "id": str(uuid.uuid4()),
                            "source": "twitter",
                            "raw_text": raw_text,
                            "date": date_formatted,
                            "url": tweet_url,
                        })

                    except Exception as e:
                        logger.debug(f"Error parsing tweet: {e}")
                        continue

                if new_found == 0:
                    no_new_count += 1
                    if no_new_count >= 3:
                        logger.info("Tidak ada tweet baru setelah 3x scroll, berhenti.")
                        break
                else:
                    no_new_count = 0

                if len(results) < limit:
                    await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                    await asyncio.sleep(2)
                    scroll_attempts += 1

            logger.info(f"Twitter scraping selesai: {len(results)} tweet ditemukan")
            return results

        except Exception as e:
            logger.error(f"Error scraping Twitter: {e}", exc_info=True)
            return results
        finally:
            await browser.close()
