"""
twitter_login.py — Login manual ke Twitter/X via Playwright + Chrome asli
==========================================================================
Menggunakan Chrome (bukan Chromium) karena X/Twitter memblokir Chromium.

Jalankan sekali: python scraper/twitter_login.py
  - Browser Chrome terbuka, Anda login sendiri (username, password, 2FA)
  - Setelah login berhasil, tekan Enter di terminal
  - Sesi disimpan ke scraper/twitter_session.json
  - Selanjutnya twitter.py akan otomatis pakai sesi ini

Usage:
    python scraper/twitter_login.py
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# Path tempat sesi disimpan
SESSION_FILE = Path(__file__).parent / "twitter_session.json"
TWITTER_LOGIN_URL = "https://x.com/i/flow/login"

# Path Chrome di Windows (cek beberapa lokasi umum)
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
try:
    import os as _os
    CHROME_PATHS.append(
        rf"C:\Users\{_os.environ.get('USERNAME','User')}\AppData\Local\Google\Chrome\Application\chrome.exe"
    )
except Exception:
    pass


def _find_chrome() -> str | None:
    """Temukan path Chrome yang terinstall."""
    for path in CHROME_PATHS:
        if Path(path).exists():
            return path
    return None


async def do_login():
    print("\n" + "=" * 60)
    print("  Twitter/X — Login Manual via Chrome (Playwright)")
    print("=" * 60)

    chrome_path = _find_chrome()
    if not chrome_path:
        print("\n[ERROR] Chrome tidak ditemukan di komputer ini.")
        print("        Install Google Chrome dari https://www.google.com/chrome/")
        return

    print(f"\n[OK] Chrome ditemukan: {chrome_path}")
    print("\n[INFO] Browser Chrome akan dibuka. Silakan login ke X (Twitter).")
    print("[INFO] Setelah berhasil login dan timeline muncul,")
    print("       kembali ke terminal ini dan tekan ENTER.\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=chrome_path,
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1150,800",
                "--start-maximized",
            ],
        )

        # Cek apakah ada sesi lama
        if SESSION_FILE.exists():
            print(f"[INFO] Sesi lama ditemukan, mencoba pakai sesi tersimpan...")
            context = await browser.new_context(
                storage_state=str(SESSION_FILE),
                viewport={"width": 1150, "height": 800},
            )
        else:
            context = await browser.new_context(
                viewport={"width": 1150, "height": 800},
            )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
        """)

        page = await context.new_page()
        await page.goto(TWITTER_LOGIN_URL, wait_until="domcontentloaded")

        print(f"[OK] Chrome dibuka di: {TWITTER_LOGIN_URL}")
        print("\n>>> Silakan login di browser Chrome yang terbuka.")
        print(">>> Selesaikan semua langkah: username → password → verifikasi.")
        print(">>> Pastikan sudah di halaman Home/For You.")
        print(">>> Setelah itu, tekan ENTER di sini.\n")

        # Tunggu user selesai login manual
        try:
            input("    Tekan ENTER setelah berhasil login... ")
        except EOFError:
            print("[WARN] Tidak ada input terminal. Tunggu 90 detik...")
            await asyncio.sleep(90)

        # Beri waktu sebentar kalau halaman lagi navigasi
        await asyncio.sleep(2)

        # Ambil URL secara aman (tanpa page.title() yang bisa gagal saat navigasi)
        current_url = page.url
        print(f"\n[INFO] URL saat ini: {current_url}")

        # Cek indikator sudah login berdasarkan URL saja
        is_logged_in = (
            "x.com" in current_url or "twitter.com" in current_url
        ) and not any(x in current_url.lower() for x in ["login", "flow", "signup"])

        # Konfirmasi tambahan via DOM (non-blocking)
        if not is_logged_in:
            try:
                await page.wait_for_selector(
                    '[data-testid="primaryColumn"], [aria-label="Home timeline"], [data-testid="AppTabBar_Home_Link"]',
                    timeout=6_000,
                )
                is_logged_in = True
                print("[INFO] Timeline terdeteksi — login berhasil!")
            except Exception:
                # Coba cek apakah ada elemen tweet di halaman
                try:
                    tweet_count = await page.locator('[data-testid="tweetText"]').count()
                    if tweet_count > 0:
                        is_logged_in = True
                except Exception:
                    pass

        if is_logged_in:
            # Simpan cookies + localStorage ke file JSON
            await context.storage_state(path=str(SESSION_FILE))
            size_kb = SESSION_FILE.stat().st_size // 1024
            print(f"\n[OK] ✓ Sesi berhasil disimpan ke: {SESSION_FILE} ({size_kb} KB)")
            print("[OK] Selanjutnya scraper akan otomatis pakai sesi ini.")
            print("[OK] Tidak perlu login lagi kecuali sesi kedaluwarsa.\n")
        else:
            print("\n[WARN] Belum terdeteksi login berhasil.")
            print("[WARN] Sesi TIDAK disimpan.")
            print("[WARN] Pastikan sudah di halaman Home, lalu jalankan script ini lagi.\n")
            # Tetap simpan saja — mungkin sesi masih valid walaupun URL aneh
            try:
                await context.storage_state(path=str(SESSION_FILE))
                print("[INFO] Sesi disimpan tetap (untuk dicoba oleh scraper).")
            except Exception:
                pass

        await context.close()
        await browser.close()


def main():
    if SESSION_FILE.exists():
        size_kb = SESSION_FILE.stat().st_size // 1024
        print(f"\n[INFO] Sesi tersimpan sudah ada: {SESSION_FILE} ({size_kb} KB)")
        resp = input("  Login ulang / buat sesi baru? [y/N]: ").strip().lower()
        if resp != "y":
            print("[OK] Pakai sesi yang sudah ada.\n")
            return

    asyncio.run(do_login())


if __name__ == "__main__":
    main()
