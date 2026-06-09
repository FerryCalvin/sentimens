"""
twitter_autologin.py — Auto-login ke X/Twitter menggunakan credentials dari .env
==================================================================================
Dipanggil otomatis oleh twitter.py saat session tidak ada / kedaluwarsa.

Flow:
  1. Baca X_USERNAME dan X_PASSWORD dari .env
  2. Buka Chrome (VISIBLE / non-headless) ke x.com/i/flow/login
     → X memblokir Chrome headless, harus visible
  3. Isi username → next → isi password → login
  4. Handle verifikasi nomor HP jika diminta (X_PHONE di .env)
  5. Simpan sesi ke twitter_session.json
"""

import asyncio
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# Muat .env dari root project (dua level di atas folder scraper)
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

logger = logging.getLogger(__name__)

SESSION_FILE = Path(__file__).parent / "twitter_session.json"
LOGIN_URL    = "https://x.com/i/flow/login"

_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
try:
    _CHROME_PATHS.append(
        rf"C:\Users\{os.environ.get('USERNAME','User')}\AppData\Local\Google\Chrome\Application\chrome.exe"
    )
except Exception:
    pass


def _find_chrome() -> str | None:
    for p in _CHROME_PATHS:
        if Path(p).exists():
            return p
    return None


async def auto_login() -> bool:
    """
    Login otomatis ke X/Twitter menggunakan credentials dari .env.
    Kembalikan True jika berhasil, False jika gagal.
    """
    username = os.getenv("X_USERNAME", "").strip()
    password = os.getenv("X_PASSWORD", "").strip()
    phone    = os.getenv("X_PHONE", "").strip()

    if not username or not password or "isi_" in username:
        logger.error(
            "X_USERNAME atau X_PASSWORD belum diisi di file .env!\n"
            f"  Edit file: {_ENV_PATH}\n"
            "  Isi X_USERNAME dan X_PASSWORD dengan akun X Anda."
        )
        return False

    chrome_path = _find_chrome()
    if not chrome_path:
        logger.error("Chrome tidak ditemukan. Install Google Chrome terlebih dahulu.")
        return False

    logger.info(f"Auto-login ke X dengan akun: {username}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=chrome_path,
            headless=False,             # HARUS visible — X memblokir Chrome headless
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1280,800",
                "--start-maximized",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="id-ID",
            timezone_id="Asia/Jakarta",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
        """)

        page = await context.new_page()

        try:
            # ── 1. Buka halaman login ────────────────────────────────────
            logger.info("Membuka halaman login X...")
            await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30_000)
            await asyncio.sleep(3)   # beri waktu JS X render form login

            # ── 2. Isi username / email ──────────────────────────────────
            logger.info("Mengisi username...")
            username_input = await page.wait_for_selector(
                'input[autocomplete="username"], input[name="text"]',
                timeout=20_000,
            )
            await username_input.click()
            await asyncio.sleep(0.5)
            await username_input.type(username, delay=80)   # ketik pelan seperti manusia
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2.5)

            # ── 3. Cek apakah X minta verifikasi nomor HP / username alt ─
            try:
                phone_input = await page.wait_for_selector(
                    'input[data-testid="ocfEnterTextTextInput"], '
                    'input[name="text"][inputmode="tel"]',
                    timeout=4_000,
                )
                if phone_input:
                    logger.info("X meminta verifikasi HP / username alternatif...")
                    verify_value = phone if phone else username
                    await phone_input.type(verify_value, delay=80)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(2.5)
            except PWTimeout:
                pass  # tidak ada verifikasi, lanjut ke password

            # ── 4. Isi password ──────────────────────────────────────────
            logger.info("Mengisi password...")
            password_input = await page.wait_for_selector(
                'input[name="password"], input[type="password"]',
                timeout=15_000,
            )
            await password_input.click()
            await asyncio.sleep(0.5)
            await password_input.type(password, delay=80)  # ketik pelan
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")

            # ── 5. Tunggu redirect ke Home ───────────────────────────────
            logger.info("Menunggu login selesai...")
            await asyncio.sleep(6)

            # Cek timeline sebagai bukti login berhasil
            try:
                await page.wait_for_selector(
                    '[data-testid="primaryColumn"], '
                    '[aria-label="Home timeline"], '
                    '[data-testid="AppTabBar_Home_Link"]',
                    timeout=15_000,
                )
                logger.info("Login berhasil! Timeline terdeteksi.")
            except PWTimeout:
                cur_url = page.url
                if any(x in cur_url.lower() for x in ["login", "flow", "signup"]):
                    logger.error(
                        f"Login GAGAL. URL: {cur_url}\n"
                        "Kemungkinan: password salah, CAPTCHA, atau 2FA aktif.\n"
                        "Coba: sentiments login  (login manual)"
                    )
                    await context.close()
                    await browser.close()
                    return False
                logger.info(f"Diasumsikan login OK. URL: {cur_url}")

            # ── 6. Simpan sesi ───────────────────────────────────────────
            await context.storage_state(path=str(SESSION_FILE))
            size_kb = SESSION_FILE.stat().st_size // 1024
            logger.info(f"Sesi disimpan → {SESSION_FILE} ({size_kb} KB)")
            await context.close()
            await browser.close()
            return True

        except Exception as e:
            logger.error(f"Error saat auto-login: {e}", exc_info=True)
            try:
                await context.close()
                await browser.close()
            except Exception:
                pass
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ok = asyncio.run(auto_login())
    if ok:
        print("\n[OK] Auto-login berhasil! Sesi disimpan.")
    else:
        print("\n[GAGAL] Auto-login gagal. Cek .env atau coba: sentiments login")
