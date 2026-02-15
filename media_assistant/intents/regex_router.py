"""Regex-based intent router for Russian voice commands."""

import re

from media_assistant.intents.types import Intent, IntentType

PATTERNS: list[tuple[str, IntentType, str | None]] = [
    (r"(?:включи|поставь|запусти)\s+(.+)", IntentType.PLAY_MEDIA, "query"),
    (r"(?:пауза|стоп|останови)", IntentType.PAUSE, None),
    (r"(?:продолжи|играй|play)", IntentType.RESUME, None),
    (r"(?:громче|прибавь звук)", IntentType.VOLUME_UP, None),
    (r"(?:тише|убавь звук)", IntentType.VOLUME_DOWN, None),
    (r"(?:громкость)\s+(\d+)", IntentType.VOLUME_SET, "level"),
    (r"(?:выключи компьютер|shutdown)", IntentType.SHUTDOWN, None),
    (r"(?:перезагрузи|перезагрузка)", IntentType.REBOOT, None),
    (r"(?:на весь экран|фулскрин|fullscreen)", IntentType.FULLSCREEN, None),
    (r"(?:закрой|выйди)", IntentType.CLOSE, None),
    (r"(?:следующ|дальше|next)", IntentType.NEXT_TRACK, None),
    (r"(?:предыдущ|назад|prev)", IntentType.PREV_TRACK, None),
]


class RegexIntentRouter:
    """Fast regex-based intent matching for known Russian commands."""

    def route(self, text: str) -> Intent:
        text = text.lower().strip()
        for pattern, intent_type, capture_name in PATTERNS:
            m = re.match(pattern, text)
            if m:
                if capture_name == "query" and m.lastindex:
                    return Intent(type=intent_type, query=m.group(1))
                elif capture_name == "level" and m.lastindex:
                    return Intent(
                        type=intent_type, params={"level": int(m.group(1))}
                    )
                return Intent(type=intent_type)
        return Intent(type=IntentType.UNKNOWN, query=text)
