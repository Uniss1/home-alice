"""Tests for media key control via win32api."""

import sys
from unittest.mock import MagicMock

import pytest

# Mock win32api/win32con before importing the module
mock_win32api = MagicMock()
mock_win32con = MagicMock()
mock_win32con.KEYEVENTF_KEYUP = 0x0002
sys.modules["win32api"] = mock_win32api
sys.modules["win32con"] = mock_win32con

# Force reimport with mocks in place
if "media_assistant.control.media_keys" in sys.modules:
    del sys.modules["media_assistant.control.media_keys"]

from media_assistant.control.media_keys import (
    press_media_key,
    play_pause,
    next_track,
    prev_track,
    VK_MEDIA_PLAY_PAUSE,
    VK_MEDIA_NEXT_TRACK,
    VK_MEDIA_PREV_TRACK,
)


@pytest.fixture(autouse=True)
def reset_mock():
    mock_win32api.reset_mock()
    yield


class TestPressMediaKey:
    def test_press_and_release(self):
        press_media_key(0xB3)
        calls = mock_win32api.keybd_event.call_args_list
        assert calls[0].args == (0xB3, 0, 0, 0)
        assert calls[1].args == (0xB3, 0, 0x0002, 0)


class TestPlayPause:
    def test_play_pause_sends_key_events(self):
        result = play_pause()
        assert mock_win32api.keybd_event.call_count == 2
        mock_win32api.keybd_event.assert_any_call(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
        mock_win32api.keybd_event.assert_any_call(VK_MEDIA_PLAY_PAUSE, 0, 0x0002, 0)
        assert "Play/Pause" in result


class TestNextTrack:
    def test_next_track_sends_key_events(self):
        result = next_track()
        mock_win32api.keybd_event.assert_any_call(VK_MEDIA_NEXT_TRACK, 0, 0, 0)
        assert "Следующий" in result


class TestPrevTrack:
    def test_prev_track_sends_key_events(self):
        result = prev_track()
        mock_win32api.keybd_event.assert_any_call(VK_MEDIA_PREV_TRACK, 0, 0, 0)
        assert "Предыдущий" in result
