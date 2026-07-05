"""
export_threads_cookies.py
==========================
Tool untuk mengekspor cookie Threads dari Chrome browser Anda
ke file scraper/threads_cookies_config.json

Caranya:
1. Buka https://www.threads.com di Chrome (pastikan sudah login)
2. Tekan F12 (DevTools) → Application → Cookies → https://www.threads.com
3. Cari "sessionid" dan "csrftoken", copy nilainya
   (ds_user_id, mid, ig_did opsional — isi jika terlihat, kosongkan jika tidak)
4. Jalankan: python export_threads_cookies.py
5. Ikuti instruksi yang muncul

CATATAN: sessionid hanya ada pada sesi yang sudah login — sesi anonim tidak
pernah mendapat cookie ini. csrftoken sesi anonim juga BEDA dengan csrftoken
sesi login, jadi wajib diambil ulang dari sesi yang sudah login, bukan dipakai
dari scraping anonim sebelumnya.
"""
import json
from pathlib import Path

COOKIES_FILE = Path(__file__).parent / "scraper" / "threads_cookies_config.json"


def manual_input():
    print()
    print("=" * 60)
    print("  Export Cookie Threads ke SentimenS")
    print("=" * 60)
    print()
    print("Langkah-langkah:")
    print("1. Buka https://www.threads.com di Chrome (pastikan sudah login)")
    print("2. Tekan F12 → tab 'Application'")
    print("3. Di sidebar kiri: Storage → Cookies → https://www.threads.com")
    print("4. Cari row dengan Name = 'sessionid' → copy Value-nya")
    print("5. Cari row dengan Name = 'csrftoken' → copy Value-nya")
    print()

    sessionid = input("Paste nilai 'sessionid' di sini: ").strip()
    if not sessionid:
        print("❌ sessionid kosong, batalkan.")
        return

    csrftoken = input("Paste nilai 'csrftoken' di sini: ").strip()
    if not csrftoken:
        print("❌ csrftoken kosong, batalkan.")
        return

    print()
    print("Opsional — kosongkan (tekan Enter) jika tidak terlihat/tidak ada:")
    ds_user_id = input("Paste nilai 'ds_user_id' (opsional): ").strip()
    mid = input("Paste nilai 'mid' (opsional): ").strip()
    ig_did = input("Paste nilai 'ig_did' (opsional): ").strip()

    cookies = {
        "sessionid":  sessionid,
        "csrftoken":  csrftoken,
        "ds_user_id": ds_user_id,
        "mid":        mid,
        "ig_did":     ig_did,
    }

    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=4)

    print()
    print(f"✅ Cookie berhasil disimpan ke {COOKIES_FILE}")
    print("   Sekarang jalankan: sentiments start")


if __name__ == "__main__":
    manual_input()
