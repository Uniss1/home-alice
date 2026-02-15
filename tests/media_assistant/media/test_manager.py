"""Tests for MediaManager."""

from unittest.mock import MagicMock

import pytest

from media_assistant.media.base import MediaProvider, MediaResult
from media_assistant.media.manager import MediaManager


@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=MediaProvider)
    provider.name = "test_provider"
    return provider


@pytest.fixture
def manager():
    return MediaManager()


class TestRegisterProvider:
    def test_register_adds_provider(self, manager, mock_provider):
        manager.register(mock_provider)
        assert "test_provider" in manager.providers

    def test_register_multiple_providers(self, manager):
        p1 = MagicMock(spec=MediaProvider)
        p1.name = "provider1"
        p2 = MagicMock(spec=MediaProvider)
        p2.name = "provider2"

        manager.register(p1)
        manager.register(p2)
        assert len(manager.providers) == 2


class TestPlaySingleResult:
    def test_play_single_result(self, manager, mock_provider):
        result = MediaResult(title="Test Video", url="http://example.com", provider="test_provider")
        mock_provider.search.return_value = [result]
        mock_provider.play.return_value = "Включаю: «Test Video»"

        manager.register(mock_provider)
        status = manager.play("test query")

        mock_provider.search.assert_called_once_with("test query")
        mock_provider.play.assert_called_once_with(result)
        assert status == "Включаю: «Test Video»"

    def test_play_sets_active_provider(self, manager, mock_provider):
        result = MediaResult(title="Test", url="http://example.com", provider="test_provider")
        mock_provider.search.return_value = [result]
        mock_provider.play.return_value = "ok"

        manager.register(mock_provider)
        manager.play("test")

        assert manager.active_provider is mock_provider


class TestPlayNoResults:
    def test_play_no_results_returns_message(self, manager, mock_provider):
        mock_provider.search.return_value = []

        manager.register(mock_provider)
        status = manager.play("несуществующий запрос")

        assert "Не нашёл" in status
        assert "несуществующий запрос" in status


class TestPlayMultipleResults:
    def test_play_multiple_results_returns_list(self, manager, mock_provider):
        results = [
            MediaResult(title="Result 1", url="http://example.com/1", provider="test_provider"),
            MediaResult(title="Result 2", url="http://example.com/2", provider="test_provider"),
        ]
        mock_provider.search.return_value = results

        manager.register(mock_provider)
        status = manager.play("ambiguous query")

        # Multiple results returned for disambiguation
        assert isinstance(status, list)
        assert len(status) == 2


class TestPlayNoProviders:
    def test_play_no_providers_returns_error(self, manager):
        status = manager.play("test")
        assert "Нет доступных" in status


class TestDelegation:
    def test_pause_delegates_to_active_provider(self, manager, mock_provider):
        mock_provider.pause.return_value = "Пауза"
        manager.active_provider = mock_provider

        status = manager.pause()
        mock_provider.pause.assert_called_once()
        assert status == "Пауза"

    def test_resume_delegates_to_active_provider(self, manager, mock_provider):
        mock_provider.resume.return_value = "Продолжаю"
        manager.active_provider = mock_provider

        status = manager.resume()
        mock_provider.resume.assert_called_once()
        assert status == "Продолжаю"

    def test_fullscreen_delegates_to_active_provider(self, manager, mock_provider):
        mock_provider.fullscreen.return_value = "Полный экран"
        manager.active_provider = mock_provider

        status = manager.fullscreen()
        mock_provider.fullscreen.assert_called_once()
        assert status == "Полный экран"

    def test_pause_no_active_provider(self, manager):
        status = manager.pause()
        assert "Нет активного" in status

    def test_resume_no_active_provider(self, manager):
        status = manager.resume()
        assert "Нет активного" in status

    def test_fullscreen_no_active_provider(self, manager):
        status = manager.fullscreen()
        assert "Нет активного" in status
