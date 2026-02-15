"""Tests for YouTubeProvider."""

from unittest.mock import MagicMock, patch

import pytest

from media_assistant.media.base import MediaResult
from media_assistant.media.youtube import YouTubeProvider


@pytest.fixture
def mock_browser():
    return MagicMock()


@pytest.fixture
def provider(mock_browser):
    return YouTubeProvider(browser=mock_browser)


class TestYouTubeSearch:
    def test_search_returns_results(self, provider, mock_browser):
        mock_page = MagicMock()
        mock_pw = MagicMock()
        mock_browser._connect.return_value = (mock_pw, MagicMock())

        # Mock browser connection to return a page with YouTube results
        mock_ctx = MagicMock()
        mock_browser._connect.return_value = (mock_pw, MagicMock(contexts=[mock_ctx]))
        mock_ctx.pages = [mock_page]

        # Simulate YouTube search result elements
        mock_element = MagicMock()
        mock_element.get_attribute.side_effect = lambda attr: {
            "href": "/watch?v=abc123",
        }.get(attr, "")
        mock_element.text_content.return_value = "Test Video Title"

        mock_page.query_selector_all.return_value = [mock_element]
        mock_page.url = "https://www.youtube.com/results?search_query=test"

        results = provider.search("test")

        assert len(results) == 1
        assert results[0].title == "Test Video Title"
        assert "watch?v=abc123" in results[0].url
        assert results[0].provider == "youtube"

    def test_search_empty_query_returns_empty(self, provider):
        results = provider.search("")
        assert results == []

    def test_search_no_results(self, provider, mock_browser):
        mock_page = MagicMock()
        mock_pw = MagicMock()
        mock_ctx = MagicMock()
        mock_browser._connect.return_value = (mock_pw, MagicMock(contexts=[mock_ctx]))
        mock_ctx.pages = [mock_page]
        mock_page.query_selector_all.return_value = []

        results = provider.search("несуществующийзапрос12345")
        assert results == []

    def test_search_limits_results(self, provider, mock_browser):
        mock_page = MagicMock()
        mock_pw = MagicMock()
        mock_ctx = MagicMock()
        mock_browser._connect.return_value = (mock_pw, MagicMock(contexts=[mock_ctx]))
        mock_ctx.pages = [mock_page]

        # Return 10 mock elements
        elements = []
        for i in range(10):
            el = MagicMock()
            el.get_attribute.side_effect = lambda attr, i=i: {
                "href": f"/watch?v=vid{i}",
            }.get(attr, "")
            el.text_content.return_value = f"Video {i}"
            elements.append(el)

        mock_page.query_selector_all.return_value = elements

        results = provider.search("test", limit=3)
        assert len(results) == 3

    def test_search_connection_error(self, provider, mock_browser):
        mock_browser._connect.side_effect = Exception("Connection refused")
        results = provider.search("test")
        assert results == []


class TestYouTubePlay:
    def test_play_navigates_and_starts(self, provider, mock_browser):
        mock_page = MagicMock()
        mock_pw = MagicMock()
        mock_ctx = MagicMock()
        mock_browser._connect.return_value = (mock_pw, MagicMock(contexts=[mock_ctx]))
        mock_ctx.pages = [mock_page]

        result = MediaResult(
            title="Interstellar",
            url="https://www.youtube.com/watch?v=abc123",
            provider="youtube",
        )
        status = provider.play(result)

        mock_page.goto.assert_called_once_with(result.url)
        assert "Interstellar" in status

    def test_play_waits_for_video_element(self, provider, mock_browser):
        mock_page = MagicMock()
        mock_pw = MagicMock()
        mock_ctx = MagicMock()
        mock_browser._connect.return_value = (mock_pw, MagicMock(contexts=[mock_ctx]))
        mock_ctx.pages = [mock_page]

        result = MediaResult(
            title="Test", url="https://www.youtube.com/watch?v=x", provider="youtube"
        )
        provider.play(result)

        mock_page.wait_for_selector.assert_called_once_with("video", timeout=10000)

    def test_play_connection_error(self, provider, mock_browser):
        mock_browser._connect.side_effect = Exception("Connection refused")
        result = MediaResult(
            title="Test", url="https://www.youtube.com/watch?v=x", provider="youtube"
        )
        status = provider.play(result)
        assert "Ошибка" in status


class TestYouTubePause:
    def test_pause_delegates_to_browser(self, provider, mock_browser):
        mock_browser.pause_video.return_value = "Поставил на паузу: «Test»"
        status = provider.pause()
        mock_browser.pause_video.assert_called_once()
        assert "паузу" in status


class TestYouTubeResume:
    def test_resume_delegates_to_browser(self, provider, mock_browser):
        mock_browser.play_video.return_value = "Продолжаю воспроизведение: «Test»"
        status = provider.resume()
        mock_browser.play_video.assert_called_once()
        assert "воспроизведение" in status


class TestYouTubeFullscreen:
    def test_fullscreen_evaluates_js(self, provider, mock_browser):
        mock_page = MagicMock()
        mock_pw = MagicMock()
        mock_ctx = MagicMock()
        mock_browser._connect.return_value = (mock_pw, MagicMock(contexts=[mock_ctx]))
        mock_ctx.pages = [mock_page]
        mock_page.evaluate.return_value = True

        status = provider.fullscreen()
        assert mock_page.evaluate.called

    def test_fullscreen_connection_error(self, provider, mock_browser):
        mock_browser._connect.side_effect = Exception("Connection refused")
        status = provider.fullscreen()
        assert "Ошибка" in status
