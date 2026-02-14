# tests/agent/tools/test_windows.py
from unittest.mock import patch, MagicMock
from agent.tools.windows import list_windows, switch_window, close_window


@patch("agent.tools.windows.win32gui")
def test_list_windows(mock_gui):
    # EnumWindows calls callback for each window
    def fake_enum(callback, _):
        callback(1001, None)
        callback(1002, None)

    mock_gui.EnumWindows.side_effect = fake_enum
    mock_gui.IsWindowVisible.return_value = True
    mock_gui.GetWindowText.side_effect = lambda h: "Chrome" if h == 1001 else "VS Code"

    result = list_windows()
    assert "Chrome" in result
    assert "VS Code" in result


@patch("agent.tools.windows.win32con")
@patch("agent.tools.windows.win32gui")
def test_switch_window(mock_gui, mock_con):
    def fake_enum(callback, _):
        callback(1001, None)

    mock_gui.EnumWindows.side_effect = fake_enum
    mock_gui.IsWindowVisible.return_value = True
    mock_gui.GetWindowText.return_value = "Google Chrome"
    mock_con.SW_RESTORE = 9

    result = switch_window("chrome")
    assert "Chrome" in result or "переключил" in result.lower()


@patch("agent.tools.windows.win32gui")
def test_switch_window_not_found(mock_gui):
    mock_gui.EnumWindows.side_effect = lambda cb, _: None
    result = switch_window("несуществующее")
    assert "не найдено" in result.lower() or "not found" in result.lower()
