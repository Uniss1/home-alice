"""YouTube media provider via Playwright CDP."""

import logging
import urllib.parse

from shared.browser import BrowserController
from media_assistant.media.base import MediaProvider, MediaResult

logger = logging.getLogger(__name__)

# CSS selector for YouTube video result links
_YT_RESULT_SELECTOR = "ytd-video-renderer a#video-title"


class YouTubeProvider(MediaProvider):
    name = "youtube"

    def __init__(self, browser: BrowserController):
        self.browser = browser

    def search(self, query: str, limit: int = 5) -> list[MediaResult]:
        """Search YouTube for videos matching query."""
        if not query.strip():
            return []

        try:
            pw, browser = self.browser._connect()
        except Exception as e:
            logger.error("Browser connection error: %s", e)
            return []

        try:
            pages = browser.contexts[0].pages if browser.contexts else []
            if not pages:
                return []

            page = pages[-1]
            encoded = urllib.parse.quote_plus(query)
            page.goto(f"https://www.youtube.com/results?search_query={encoded}")
            page.wait_for_selector(_YT_RESULT_SELECTOR, timeout=10000)

            elements = page.query_selector_all(_YT_RESULT_SELECTOR)
            results = []
            for el in elements[:limit]:
                href = el.get_attribute("href") or ""
                title = el.text_content() or ""
                title = title.strip()
                if not href or not title:
                    continue
                if href.startswith("/"):
                    href = f"https://www.youtube.com{href}"
                results.append(
                    MediaResult(title=title, url=href, provider="youtube")
                )

            return results
        except Exception as e:
            logger.error("YouTube search error: %s", e)
            return []
        finally:
            pw.__exit__(None, None, None)

    def play(self, result: MediaResult) -> str:
        """Navigate to video and start playback."""
        try:
            pw, browser = self.browser._connect()
        except Exception as e:
            logger.error("Browser connection error: %s", e)
            return f"Ошибка подключения к браузеру: {e}"

        try:
            pages = browser.contexts[0].pages if browser.contexts else []
            if not pages:
                return "Нет открытых вкладок"

            page = pages[-1]
            page.goto(result.url)
            page.wait_for_selector("video", timeout=10000)
            page.evaluate("document.querySelector('video').play()")
            return f"Включаю: «{result.title}»"
        except Exception as e:
            logger.error("YouTube play error: %s", e)
            return f"Ошибка воспроизведения: {e}"
        finally:
            pw.__exit__(None, None, None)

    def pause(self) -> str:
        """Pause current playback."""
        return self.browser.pause_video()

    def resume(self) -> str:
        """Resume current playback."""
        return self.browser.play_video()

    def fullscreen(self) -> str:
        """Toggle fullscreen on the current video."""
        try:
            pw, browser = self.browser._connect()
        except Exception as e:
            logger.error("Browser connection error: %s", e)
            return f"Ошибка подключения к браузеру: {e}"

        try:
            pages = browser.contexts[0].pages if browser.contexts else []
            for page in pages:
                has_video = page.evaluate("!!document.querySelector('video')")
                if has_video:
                    page.evaluate(
                        "document.querySelector('video').requestFullscreen()"
                    )
                    return "Полный экран"
            return "Не нашёл видео"
        except Exception as e:
            logger.error("Fullscreen error: %s", e)
            return f"Ошибка: {e}"
        finally:
            pw.__exit__(None, None, None)
