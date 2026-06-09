"""
export_twitter_cookies.py
=========================
Tool untuk mengekspor cookie X/Twitter dari Chrome browser Anda
ke file scraper/cookies_config.json

Caranya:
1. Pastikan Anda sudah login di Chrome ke x.com
2. Jalankan: python export_twitter_cookies.py
3. Ikuti instruksi yang muncul

Atau cara manual (lebih mudah):
1. Buka x.com di Chrome
2. Tekan F12 (DevTools) → Application → Cookies → https://x.com
3. Cari "auth_token" dan "ct0", copy nilainya
4. Paste ke scraper/cookies_config.json
"""
import json
import sys
from pathlib import Path

COOKIES_FILE = Path(__file__).parent / "scraper" / "cookies_config.json"


def manual_input():
    print()
    print("=" * 60)
    print("  Export Cookie X/Twitter ke SentimenS")
    print("=" * 60)
    print()
    print("Langkah-langkah:")
    print("1. Buka https://x.com di Chrome (pastikan sudah login)")
    print("2. Tekan F12 → tab 'Application'")
    print("3. Di sidebar kiri: Storage → Cookies → https://x.com")
    print("4. Cari row dengan Name = 'auth_token' → copy Value-nya")
    print("5. Cari row dengan Name = 'ct0' → copy Value-nya")
    print()

    auth_token = input("Paste nilai 'auth_token' di sini: ").strip()
    if not auth_token:
        print("❌ auth_token kosong, batalkan.")
        return

    ct0 = input("Paste nilai 'ct0' di sini: ").strip()
    if not ct0:
        print("❌ ct0 kosong, batalkan.")
        return

    cookies = {
        "auth_token": auth_token,
        "ct0":        ct0,
        "guest_id":   "",
        "twid":       "",
        "gt":         "",
    }

    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=4)

    print()
    print(f"✅ Cookie berhasil disimpan ke {COOKIES_FILE}")
    print("   Sekarang jalankan: sentiments start")


if __name__ == "__main__":
    manual_input()
