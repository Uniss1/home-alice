# agent/tools/keyboard.py
import logging

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    # Create a minimal mock for testing on non-Windows systems
    class _MockPyAutoGUI:
        FAILSAFE = False
        def hotkey(self, *args): pass
        def write(self, *args, **kwargs): pass
    pyautogui = _MockPyAutoGUI()

logger = logging.getLogger(__name__)


def press_keys(keys: list[str]) -> str:
    try:
        pyautogui.hotkey(*keys)
        return f"Нажал {'+'.join(keys)}"
    except Exception as e:
        return f"Ошибка: {e}"


def type_text(text: str) -> str:
    try:
        pyautogui.write(text, interval=0.02)
        return f"Напечатал текст"
    except Exception as e:
        return f"Ошибка: {e}"
