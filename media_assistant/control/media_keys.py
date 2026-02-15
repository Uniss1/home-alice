"""Media key control via win32api."""

try:
    import win32api
    import win32con
except ImportError:
    win32api = None
    win32con = None

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF


def press_media_key(vk_code: int) -> None:
    """Press and release a media key."""
    win32api.keybd_event(vk_code, 0, 0, 0)
    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)


def play_pause() -> str:
    press_media_key(VK_MEDIA_PLAY_PAUSE)
    return "Play/Pause"


def next_track() -> str:
    press_media_key(VK_MEDIA_NEXT_TRACK)
    return "Следующий трек"


def prev_track() -> str:
    press_media_key(VK_MEDIA_PREV_TRACK)
    return "Предыдущий трек"
