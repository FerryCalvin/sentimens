"""
browser_manager.py — Persistent Chromium browser shared across scrape requests
================================================================================
Sebelumnya tiap fungsi scraping (twitter.py, threads.py, web_search.py) membuka
`async_playwright()` + `chromium.launch()` sendiri-sendiri per panggilan, dan
`main.py` bahkan membuat event loop asyncio baru per request Flask — hasilnya
2-5 instance Chromium baru tiap kali endpoint /scrape dipanggil.

Modul ini menjalankan SATU thread background dengan SATU event loop asyncio
yang hidup selama proses berjalan, dan SATU `Browser` Chromium yang di-launch
sekali lalu dipakai ulang. Setiap request cukup minta `new_context()` (context
baru, terisolasi cookie/state-nya, ditutup pemanggil setelah selesai) —
`Browser`-nya sendiri tetap warm lintas request.

Karena objek Playwright terikat ke event loop yang membuatnya, SEMUA coroutine
yang menyentuh browser bersama ini (termasuk seluruh `_scrape_parallel(...)`)
harus dijalankan lewat `manager.run_coroutine(...)`, bukan `asyncio.run()`/loop
baru per request.
"""
import asyncio
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
try:
    _CHROME_PATHS.append(
        rf"C:\Users\{os.environ.get('USERNAME', 'User')}\AppData\Local\Google\Chrome\Application\chrome.exe"
    )
    _CHROME_PATHS.append(
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe")
    )
except Exception:
    pass

_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--window-size=1280,900",
    "--disable-dev-shm-usage",
]


def find_chrome() -> str | None:
    for p in _CHROME_PATHS:
        if p and Path(p).exists():
            return p
    return None


class _BrowserManager:
    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._playwright = None
        self._browser = None
        self._lock: asyncio.Lock | None = None
        self._start_lock = threading.Lock()

    def ensure_started(self) -> None:
        """Idempotent: start the background loop thread once (safe to call from any thread)."""
        if self._thread is not None:
            return
        with self._start_lock:
            if self._thread is not None:
                return
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="browser-manager-loop")
            self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run_coroutine(self, coro, timeout: float | None = None):
        """Bridge a coroutine from a sync caller (Flask request thread) onto the shared loop."""
        self.ensure_started()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise

    async def _relaunch(self) -> None:
        from playwright.async_api import async_playwright

        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        chrome_path = find_chrome()
        launch_kwargs = {"headless": True, "args": _LAUNCH_ARGS}
        if chrome_path:
            launch_kwargs["executable_path"] = chrome_path
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        logger.info(f"[BrowserManager] Chromium (re)launched — {chrome_path or 'bundled build'}")

    async def get_browser(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if self._browser is None or not self._browser.is_connected():
                if self._browser is not None:
                    logger.warning("[BrowserManager] Browser disconnected — relaunching.")
                await self._relaunch()
            return self._browser

    async def new_context(self, **kwargs):
        """Fresh isolated BrowserContext from the shared Browser. Retries once via relaunch on failure."""
        browser = await self.get_browser()
        try:
            return await browser.new_context(**kwargs)
        except Exception as e:
            logger.warning(f"[BrowserManager] new_context gagal ({e}) — relaunch & retry sekali.")
            self._browser = None
            browser = await self.get_browser()
            return await browser.new_context(**kwargs)

    async def shutdown_async(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def shutdown(self) -> None:
        """Graceful shutdown for normal process exit (does not cover a hard kill)."""
        if self._loop is None or self._thread is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.shutdown_async(), self._loop).result(timeout=10)
        except Exception as e:
            logger.warning(f"[BrowserManager] shutdown_async gagal: {e}")
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)


manager = _BrowserManager()
