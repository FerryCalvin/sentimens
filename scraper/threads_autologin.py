"""
threads_autologin.py — Auto-login ke Threads menggunakan credentials dari .env
==================================================================================
Dipanggil manual (python scraper/threads_autologin.py) sebagai alternatif
threads_login.py (manual) saat Anda ingin login otomatis tanpa mengetik sendiri.

Flow:
  1. Baca THREADS_USERNAME dan THREADS_PASSWORD dari .env
  2. Buka Chrome (VISIBLE / non-headless) ke threads.com/login
  3. Isi username + password (form Instagram/Meta — satu halaman, bukan dua step)
  4. Deteksi checkpoint/verifikasi Meta (kode email/SMS) — TIDAK bisa diselesaikan
     otomatis, berhenti dan minta login manual (threads_login.py) jika terjadi
  5. Simpan sesi ke threads_session.json
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

SESSION_FILE = Path(__file__).parent / "threads_session.json"
LOGIN_URL    = "https://www.threads.com/login"

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
    Login otomatis ke Threads menggunakan credentials dari .env.
    Kembalikan True jika berhasil, False jika gagal.
    """
    username = os.getenv("THREADS_USERNAME", "").strip()
    password = os.getenv("THREADS_PASSWORD", "").strip()

    if not username or not password or "isi_" in username:
        logger.error(
            "THREADS_USERNAME atau THREADS_PASSWORD belum diisi di file .env!\n"
            f"  Edit file: {_ENV_PATH}\n"
            "  Isi THREADS_USERNAME dan THREADS_PASSWORD dengan akun Threads Anda."
        )
        return False

    chrome_path = _find_chrome()
    if not chrome_path:
        logger.error("Chrome tidak ditemukan. Install Google Chrome terlebih dahulu.")
        return False

    logger.info(f"Auto-login ke Threads dengan akun: {username}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=chrome_path,
            headless=False,             # visible — mengurangi risiko deteksi bot
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
            logger.info("Membuka halaman login Threads...")
            await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30_000)
            await asyncio.sleep(3)   # beri waktu JS render form login

            # ── 2. Isi username + password (form satu halaman, gaya Meta) ─
            logger.info("Mengisi username...")
            username_input = await page.wait_for_selector(
                'input[name="username"], input[autocomplete="username"], input[type="text"]',
                timeout=20_000,
            )
            await username_input.click()
            await asyncio.sleep(0.5)
            await username_input.type(username, delay=80)   # ketik pelan seperti manusia

            logger.info("Mengisi password...")
            password_input = await page.wait_for_selector(
                'input[name="password"], input[type="password"]',
                timeout=10_000,
            )
            await password_input.click()
            await asyncio.sleep(0.5)
            await password_input.type(password, delay=80)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")

            # ── 3. Tunggu redirect / deteksi checkpoint ──────────────────
            logger.info("Menunggu login selesai...")
            await asyncio.sleep(6)

            cur_url = page.url.lower()
            if any(x in cur_url for x in ["challenge", "checkpoint", "two_factor", "auth_platform"]):
                logger.error(
                    f"Threads/Meta meminta verifikasi tambahan (checkpoint). URL: {page.url}\n"
                    "Ini TIDAK bisa diselesaikan otomatis (butuh kode email/SMS manual).\n"
                    "Selesaikan verifikasi di jendela Chrome yang terbuka, lalu tekan ENTER di sini "
                    "untuk tetap menyimpan sesi setelah Anda selesai — atau tutup dan pakai "
                    "threads_login.py (manual) sebagai gantinya."
                )
                try:
                    input("    Tekan ENTER setelah verifikasi selesai (atau Ctrl+C untuk batal)... ")
                except EOFError:
                    await context.close()
                    await browser.close()
                    return False
                await asyncio.sleep(2)
                cur_url = page.url.lower()

            # Cek indikator sudah login berdasarkan URL
            is_logged_in = "threads.com" in cur_url and not any(
                x in cur_url for x in ["login", "challenge", "checkpoint"]
            )

            if not is_logged_in:
                try:
                    await page.wait_for_selector(
                        '[aria-label="Search"], [aria-label="Home"], svg[aria-label="Create"]',
                        timeout=10_000,
                    )
                    is_logged_in = True
                    logger.info("Elemen feed terdeteksi — login berhasil!")
                except PWTimeout:
                    pass

            if not is_logged_in:
                logger.error(
                    f"Login GAGAL atau tidak terverifikasi. URL: {page.url}\n"
                    "Kemungkinan: username/password salah, atau checkpoint belum selesai.\n"
                    "Coba: python scraper/threads_login.py  (login manual)"
                )
                await context.close()
                await browser.close()
                return False

            # ── 4. Simpan sesi ───────────────────────────────────────────
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
        print("\n[GAGAL] Auto-login gagal. Cek .env atau coba: python scraper/threads_login.py")
