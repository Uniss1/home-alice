"""Abstract base for media providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MediaResult:
    title: str
    url: str
    provider: str
    thumbnail: str = ""


class MediaProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[MediaResult]:
        """Search for media by query."""

    @abstractmethod
    def play(self, result: MediaResult) -> str:
        """Navigate to media and start playback. Return status message."""

    @abstractmethod
    def pause(self) -> str:
        """Pause current playback."""

    @abstractmethod
    def resume(self) -> str:
        """Resume current playback."""

    @abstractmethod
    def fullscreen(self) -> str:
        """Toggle fullscreen."""
