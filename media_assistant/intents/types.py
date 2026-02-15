"""Intent types for media assistant commands."""

from dataclasses import dataclass, field
from enum import Enum


class IntentType(Enum):
    PLAY_MEDIA = "play_media"
    PAUSE = "pause"
    RESUME = "resume"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_SET = "volume_set"
    SHUTDOWN = "shutdown"
    REBOOT = "reboot"
    FULLSCREEN = "fullscreen"
    CLOSE = "close"
    NEXT_TRACK = "next_track"
    PREV_TRACK = "prev_track"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    type: IntentType
    query: str = ""
    params: dict = field(default_factory=dict)
