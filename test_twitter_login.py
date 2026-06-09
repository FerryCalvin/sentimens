"""
Script debug: Test login Twitter dengan tampilkan screenshot halaman login
Jalankan: python test_twitter_login.py
"""
import asyncio
import os
from playwright.async_api import async_playwright

TWITTER_USERNAME = "nanashi_dono"   # tanpa @
TWITTER_PASSWORD = "@Ferrycalvin12345#"

async def test_login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # TAMPILKAN browser untuk debug
            slow_mo=500,
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        page = await context.new_page()

        print("Membuka halaman login Twitter...")
        await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)

        print(f"URL: {page.url}")
        print(f"Title: {await page.title()}")

        # Ambil semua input elements
        inputs = await page.query_selector_all("input")
        print(f"\nJumlah input ditemukan: {len(inputs)}")
        for i, inp in enumerate(inputs):
            try:
                typ = await inp.get_attribute("type")
                name = await inp.get_attribute("name")
                auto = await inp.get_attribute("autocomplete")
                placeholder = await inp.get_attribute("placeholder")
                print(f"  input[{i}]: type={typ}, name={name}, autocomplete={auto}, placeholder={placeholder}")
            except Exception as e:
                print(f"  input[{i}]: error {e}")

        # Screenshot
        await page.screenshot(path="debug_login.png")
        print("\nScreenshot disimpan: debug_login.png")

        # Coba isi username
        print("\nMencoba isi username...")
        username_selectors = [
            'input[autocomplete="username"]',
            'input[name="text"]',
            'input[type="text"]',
        ]
        username_input = None
        for sel in username_selectors:
            try:
                inp = await page.query_selector(sel)
                if inp:
                    username_input = inp
                    print(f"Username input ditemukan: {sel}")
                    break
            except Exception:
                continue

        if username_input:
            await username_input.fill(TWITTER_USERNAME)
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(3)
            print(f"URL setelah username: {page.url}")
            await page.screenshot(path="debug_after_username.png")

            # Coba isi password
            pwd_input = await page.query_selector('input[name="password"], input[type="password"]')
            if pwd_input:
                await pwd_input.fill(TWITTER_PASSWORD)
                await asyncio.sleep(1)
                await page.keyboard.press("Enter")
                await asyncio.sleep(5)
                print(f"URL setelah login: {page.url}")
                await page.screenshot(path="debug_after_login.png")
                print("Semua screenshot tersimpan!")
            else:
                print("PASSWORD INPUT TIDAK DITEMUKAN!")
                # Cek apakah ada konfirmasi identitas
                all_inputs = await page.query_selector_all("input")
                for i, inp in enumerate(all_inputs):
                    typ = await inp.get_attribute("type")
                    name = await inp.get_attribute("name")
                    auto = await inp.get_attribute("autocomplete")
                    print(f"  input[{i}]: type={typ}, name={name}, autocomplete={auto}")
                await page.screenshot(path="debug_step2.png")
        else:
            print("USERNAME INPUT TIDAK DITEMUKAN!")

        await asyncio.sleep(3)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_login())
