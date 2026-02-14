# agent/tools/windows.py
import logging

try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None
    win32con = None

logger = logging.getLogger(__name__)


def _get_visible_windows() -> list[tuple[int, str]]:
    if not win32gui:
        return []
    windows = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                windows.append((hwnd, title))

    win32gui.EnumWindows(callback, None)
    return windows


def list_windows() -> str:
    windows = _get_visible_windows()
    if not windows:
        return "Нет открытых окон"
    lines = [f"- {title}" for _, title in windows]
    return "Открытые окна:\n" + "\n".join(lines)


def switch_window(title: str) -> str:
    windows = _get_visible_windows()
    title_lower = title.lower()
    for hwnd, wnd_title in windows:
        if title_lower in wnd_title.lower():
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                return f"Переключил на «{wnd_title}»"
            except Exception as e:
                return f"Ошибка при переключении: {e}"
    return f"Окно «{title}» не найдено"


def close_window(title: str) -> str:
    windows = _get_visible_windows()
    title_lower = title.lower()
    for hwnd, wnd_title in windows:
        if title_lower in wnd_title.lower():
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return f"Закрыл «{wnd_title}»"
            except Exception as e:
                return f"Ошибка: {e}"
    return f"Окно «{title}» не найдено"
