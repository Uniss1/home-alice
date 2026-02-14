# agent/tools/browser_control.py
import logging

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

logger = logging.getLogger(__name__)

# CSS selectors to find search inputs on pages
_SEARCH_SELECTORS = [
    'input[type="search"]',
    'input[name="search"]',
    'input[name="q"]',
    'input[name="query"]',
    'input[aria-label*="поиск" i]',
    'input[aria-label*="search" i]',
    'input[placeholder*="поиск" i]',
    'input[placeholder*="search" i]',
]


class BrowserController:
    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url

    def _connect(self):
        """Connect to browser via CDP and return (playwright, browser)."""
        pw = sync_playwright().__enter__()
        browser = pw.chromium.connect_over_cdp(self.cdp_url)
        return pw, browser

    def list_tabs(self) -> str:
        try:
            pw, browser = self._connect()
        except Exception as e:
            logger.error("Browser connection error: %s", e)
            return f"Ошибка подключения к браузеру: {e}"

        try:
            pages = browser.contexts[0].pages if browser.contexts else []
            if not pages:
                return "Нет открытых вкладок"

            lines = []
            for i, page in enumerate(pages, 1):
                title = page.title()
                url = page.url
                has_video = page.evaluate("!!document.querySelector('video')")
                if has_video:
                    is_paused = page.evaluate("document.querySelector('video').paused")
                    marker = "⏸" if is_paused else "▶"
                    lines.append(f"{i}. {marker} {title} — {url}")
                else:
                    lines.append(f"{i}. {title} — {url}")

            return "Вкладки:\n" + "\n".join(lines)
        finally:
            pw.__exit__(None, None, None)

    def pause_video(self) -> str:
        try:
            pw, browser = self._connect()
        except Exception as e:
            logger.error("Browser connection error: %s", e)
            return f"Ошибка подключения к браузеру: {e}"

        try:
            pages = browser.contexts[0].pages if browser.contexts else []
            for page in pages:
                has_video = page.evaluate("!!document.querySelector('video')")
                if not has_video:
                    continue
                is_paused = page.evaluate("document.querySelector('video').paused")
                if not is_paused:
                    page.evaluate("document.querySelector('video').pause()")
                    title = page.title()
                    return f"Поставил на паузу: «{title}»"

            return "Не нашёл играющее видео ни в одной вкладке"
        finally:
            pw.__exit__(None, None, None)

    def play_video(self) -> str:
        try:
            pw, browser = self._connect()
        except Exception as e:
            logger.error("Browser connection error: %s", e)
            return f"Ошибка подключения к браузеру: {e}"

        try:
            pages = browser.contexts[0].pages if browser.contexts else []
            for page in pages:
                has_video = page.evaluate("!!document.querySelector('video')")
                if not has_video:
                    continue
                is_paused = page.evaluate("document.querySelector('video').paused")
                if is_paused:
                    page.evaluate("document.querySelector('video').play()")
                    title = page.title()
                    return f"Продолжаю воспроизведение: «{title}»"

            return "Не нашёл видео на паузе ни в одной вкладке"
        finally:
            pw.__exit__(None, None, None)

    def search(self, query: str) -> str:
        if not query.strip():
            return "Укажи что искать — запрос пустой"

        try:
            pw, browser = self._connect()
        except Exception as e:
            logger.error("Browser connection error: %s", e)
            return f"Ошибка подключения к браузеру: {e}"

        try:
            pages = browser.contexts[0].pages if browser.contexts else []
            if not pages:
                return "Нет открытых вкладок"

            # Use the active (last) page
            page = pages[-1]

            # Try each search selector
            for selector in _SEARCH_SELECTORS:
                element = page.query_selector(selector)
                if element:
                    element.fill(query)
                    element.press("Enter")
                    return f"Ищу «{query}»"

            return "Не нашёл поле поиска на странице"
        finally:
            pw.__exit__(None, None, None)
