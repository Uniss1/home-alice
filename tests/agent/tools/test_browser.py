# tests/agent/tools/test_browser.py
from unittest.mock import patch, MagicMock
from agent.tools.browser import open_url, search_vk_video


@patch("agent.tools.browser.webbrowser.open")
def test_open_url(mock_open):
    result = open_url("https://vk.com/video123")
    mock_open.assert_called_once_with("https://vk.com/video123")
    assert "открываю" in result.lower() or "open" in result.lower()


@patch("agent.tools.browser.webbrowser.open", side_effect=Exception("No browser"))
def test_open_url_failure(mock_open):
    result = open_url("https://example.com")
    assert "ошибка" in result.lower() or "error" in result.lower()


@patch("agent.tools.browser.webbrowser.open")
@patch("agent.tools.browser.httpx.Client")
def test_search_vk_video(mock_client_cls, mock_browser_open):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
    mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": {
            "count": 1,
            "items": [{"id": 456, "owner_id": -123, "title": "Test", "views": 1000}],
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.get = MagicMock(return_value=mock_response)

    result = search_vk_video("котики", vk_token="test-token")
    assert "vk.com" in result
    mock_browser_open.assert_called_once_with("https://vk.com/video-123_456")


@patch("agent.tools.browser.httpx.Client")
def test_search_vk_video_no_results(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
    mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": {
            "count": 0,
            "items": [],
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.get = MagicMock(return_value=mock_response)

    result = search_vk_video("несуществующее видео", vk_token="test-token")
    assert "не нашла" in result.lower()


@patch("agent.tools.browser.httpx.Client")
def test_search_vk_video_api_error(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
    mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
    mock_client.get = MagicMock(side_effect=Exception("API Error"))

    result = search_vk_video("котики", vk_token="test-token")
    assert "ошибка" in result.lower()


@patch("agent.tools.browser.webbrowser.open")
@patch("agent.tools.browser.httpx.Client")
def test_search_vk_video_with_channel_id(mock_client_cls, mock_browser_open):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
    mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": {
            "count": 1,
            "items": [{"id": 789, "owner_id": -999, "title": "Channel Video", "views": 500}],
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.get = MagicMock(return_value=mock_response)

    result = search_vk_video("котики", vk_token="test-token", channel_id=-999)
    assert "vk.com" in result
    # Verify that owner_id was passed in params
    call_args = mock_client.get.call_args
    assert call_args[1]["params"]["owner_id"] == -999
