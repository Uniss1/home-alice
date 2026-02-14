# tests/agent/tools/test_keyboard.py
from unittest.mock import patch
from agent.tools.keyboard import press_keys, type_text


@patch("agent.tools.keyboard.pyautogui.hotkey")
def test_press_keys(mock_hotkey):
    result = press_keys(["ctrl", "c"])
    mock_hotkey.assert_called_once_with("ctrl", "c")
    assert "нажал" in result.lower() or "pressed" in result.lower()


@patch("agent.tools.keyboard.pyautogui.write")
def test_type_text(mock_write):
    result = type_text("hello world")
    mock_write.assert_called_once_with("hello world", interval=0.02)
    assert "напечатал" in result.lower() or "typed" in result.lower()


@patch("agent.tools.keyboard.pyautogui.hotkey")
def test_press_keys_handles_exception(mock_hotkey):
    mock_hotkey.side_effect = Exception("Test error")
    result = press_keys(["ctrl", "c"])
    assert "ошибка" in result.lower() or "error" in result.lower()


@patch("agent.tools.keyboard.pyautogui.write")
def test_type_text_handles_exception(mock_write):
    mock_write.side_effect = Exception("Test error")
    result = type_text("test")
    assert "ошибка" in result.lower() or "error" in result.lower()
