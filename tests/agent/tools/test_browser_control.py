# tests/agent/tools/test_browser_control.py
from unittest.mock import patch, MagicMock, PropertyMock
import pytest
from agent.tools.browser_control import BrowserController


@pytest.fixture
def mock_playwright():
    """Set up mocked Playwright with browser, context, and pages."""
    with patch("agent.tools.browser_control.sync_playwright") as mock_sp:
        mock_pw = MagicMock()
        mock_sp.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_sp.return_value.__exit__ = MagicMock(return_value=False)

        mock_browser = MagicMock()
        mock_pw.chromium.connect_over_cdp.return_value = mock_browser

        mock_context = MagicMock()
        mock_browser.contexts = [mock_context]

        yield {
            "sync_playwright": mock_sp,
            "pw": mock_pw,
            "browser": mock_browser,
            "context": mock_context,
        }


def _make_page(title: str, url: str, has_video: bool = False, video_paused: bool = True):
    """Helper to create a mock page."""
    page = MagicMock()
    page.title.return_value = title
    page.url = url

    def evaluate_side_effect(script):
        if "!!document.querySelector('video')" in script:
            return has_video
        if "document.querySelector('video').paused" in script:
            return video_paused
        if ".pause()" in script:
            return None
        if ".play()" in script:
            return None
        return None

    page.evaluate.side_effect = evaluate_side_effect
    return page


class TestListTabs:
    def test_returns_tab_list(self, mock_playwright):
        pages = [
            _make_page("YouTube - Funny Cat", "https://youtube.com/watch?v=123", has_video=True, video_paused=False),
            _make_page("Google", "https://google.com"),
        ]
        mock_playwright["context"].pages = pages

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.list_tabs()

        assert "YouTube - Funny Cat" in result
        assert "Google" in result

    def test_returns_video_indicator(self, mock_playwright):
        pages = [
            _make_page("VK Video", "https://vk.com/video", has_video=True, video_paused=False),
            _make_page("Habr", "https://habr.com"),
        ]
        mock_playwright["context"].pages = pages

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.list_tabs()

        # Tab with playing video should be marked
        assert "▶" in result or "видео" in result.lower()

    def test_no_tabs(self, mock_playwright):
        mock_playwright["context"].pages = []

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.list_tabs()

        assert "нет" in result.lower() or "пуст" in result.lower()

    def test_connection_error(self, mock_playwright):
        mock_playwright["pw"].chromium.connect_over_cdp.side_effect = Exception("Connection refused")

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.list_tabs()

        assert "ошибка" in result.lower()


class TestPauseVideo:
    def test_pauses_playing_video(self, mock_playwright):
        page = _make_page("YouTube", "https://youtube.com", has_video=True, video_paused=False)
        mock_playwright["context"].pages = [page]

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.pause_video()

        # Should have called evaluate with .pause()
        calls = [str(c) for c in page.evaluate.call_args_list]
        assert any(".pause()" in c for c in calls)
        assert "пауз" in result.lower()

    def test_no_video_playing(self, mock_playwright):
        page = _make_page("Google", "https://google.com", has_video=False)
        mock_playwright["context"].pages = [page]

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.pause_video()

        assert "не нашёл" in result.lower()

    def test_video_already_paused(self, mock_playwright):
        page = _make_page("YouTube", "https://youtube.com", has_video=True, video_paused=True)
        mock_playwright["context"].pages = [page]

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.pause_video()

        assert "не нашёл" in result.lower()


class TestPlayVideo:
    def test_plays_paused_video(self, mock_playwright):
        page = _make_page("YouTube", "https://youtube.com", has_video=True, video_paused=True)
        mock_playwright["context"].pages = [page]

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.play_video()

        calls = [str(c) for c in page.evaluate.call_args_list]
        assert any(".play()" in c for c in calls)
        assert "продолж" in result.lower() or "воспроизв" in result.lower()

    def test_no_paused_video(self, mock_playwright):
        page = _make_page("Google", "https://google.com", has_video=False)
        mock_playwright["context"].pages = [page]

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.play_video()

        assert "не нашёл" in result.lower()


class TestBrowserSearch:
    def test_searches_on_current_page(self, mock_playwright):
        page = _make_page("Google", "https://google.com")
        # For search: first check for input, then fill and submit
        page.query_selector.return_value = MagicMock()  # search input exists
        mock_playwright["context"].pages = [page]

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.search("котики")

        assert "кот" in result.lower() or "ищу" in result.lower() or "поиск" in result.lower()

    def test_search_no_input_found(self, mock_playwright):
        page = _make_page("Some Page", "https://example.com")
        page.query_selector.return_value = None  # no search input
        mock_playwright["context"].pages = [page]

        ctrl = BrowserController("http://localhost:9222")
        result = ctrl.search("котики")

        assert "не нашёл" in result.lower()

    def test_search_empty_query(self, mock_playwright):
        ctrl = BrowserController("http://localhost:9222")
        mock_playwright["context"].pages = [_make_page("Google", "https://google.com")]

        result = ctrl.search("")

        assert "пуст" in result.lower() or "укажи" in result.lower()
