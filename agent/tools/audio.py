# agent/tools/audio.py
import logging

logger = logging.getLogger(__name__)


def _get_volume_interface():
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def volume_set(level: int) -> str:
    try:
        vol = _get_volume_interface()
        vol.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100.0, None)
        return f"Громкость: {level}%"
    except Exception as e:
        return f"Ошибка: {e}"


def volume_mute(mute: bool) -> str:
    try:
        vol = _get_volume_interface()
        vol.SetMute(1 if mute else 0, None)
        return "Звук выключен" if mute else "Звук включён"
    except Exception as e:
        return f"Ошибка: {e}"
