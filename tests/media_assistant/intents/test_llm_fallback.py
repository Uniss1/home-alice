"""Tests for LLMFallbackRouter with mocked httpx."""

from unittest.mock import MagicMock, patch
import pytest

from media_assistant.intents.types import IntentType
from media_assistant.intents.llm_fallback import LLMFallbackRouter


class TestLLMFallbackParsesToolCall:
    @patch("media_assistant.intents.llm_fallback.httpx")
    def test_parses_play_media_tool_call(self, mock_httpx):
        """LLM returns tool call → correct Intent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "tool_calls": [
                    {
                        "function": {
                            "name": "play_media",
                            "arguments": {"query": "интерстеллар"},
                        }
                    }
                ]
            }
        }
        mock_httpx.post.return_value = mock_response

        router = LLMFallbackRouter()
        intent = router.route("поставь фильм интерстеллар")

        assert intent.type == IntentType.PLAY_MEDIA
        assert intent.query == "интерстеллар"

    @patch("media_assistant.intents.llm_fallback.httpx")
    def test_parses_pause_tool_call(self, mock_httpx):
        """LLM returns pause tool call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "tool_calls": [
                    {
                        "function": {
                            "name": "pause",
                            "arguments": {},
                        }
                    }
                ]
            }
        }
        mock_httpx.post.return_value = mock_response

        router = LLMFallbackRouter()
        intent = router.route("поставь на паузу")

        assert intent.type == IntentType.PAUSE


class TestLLMFallbackTimeout:
    @patch("media_assistant.intents.llm_fallback.httpx")
    def test_timeout_returns_unknown(self, mock_httpx):
        """Ollama timeout → UNKNOWN intent."""
        import httpx
        mock_httpx.post.side_effect = httpx.TimeoutException("timeout")
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.ConnectError = httpx.ConnectError

        router = LLMFallbackRouter()
        intent = router.route("что-то непонятное")

        assert intent.type == IntentType.UNKNOWN

    @patch("media_assistant.intents.llm_fallback.httpx")
    def test_no_tool_calls_returns_unknown(self, mock_httpx):
        """LLM responds without tool call → UNKNOWN intent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Не понимаю команду"}
        }
        mock_httpx.post.return_value = mock_response

        router = LLMFallbackRouter()
        intent = router.route("абракадабра")

        assert intent.type == IntentType.UNKNOWN


class TestIsAvailable:
    @patch("media_assistant.intents.llm_fallback.httpx")
    def test_available_when_ollama_running(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx.get.return_value = mock_response

        router = LLMFallbackRouter()
        assert router.is_available() is True

    @patch("media_assistant.intents.llm_fallback.httpx")
    def test_unavailable_when_connection_error(self, mock_httpx):
        import httpx
        mock_httpx.get.side_effect = httpx.ConnectError("refused")
        mock_httpx.ConnectError = httpx.ConnectError

        router = LLMFallbackRouter()
        assert router.is_available() is False
