"""Media provider manager — registry and delegation."""

from media_assistant.media.base import MediaProvider, MediaResult


class MediaManager:
    def __init__(self):
        self.providers: dict[str, MediaProvider] = {}
        self.active_provider: MediaProvider | None = None

    def register(self, provider: MediaProvider) -> None:
        """Register a media provider."""
        self.providers[provider.name] = provider

    def play(self, query: str) -> str | list[MediaResult]:
        """Search across providers, play best result."""
        if not self.providers:
            return "Нет доступных провайдеров"

        # For now: use first registered provider
        provider = next(iter(self.providers.values()))
        results = provider.search(query)

        if not results:
            return f"Не нашёл «{query}»"

        if len(results) == 1:
            self.active_provider = provider
            return provider.play(results[0])

        # Multiple results — return list for disambiguation by orchestrator
        return results

    def pause(self) -> str:
        """Pause active provider playback."""
        if self.active_provider is None:
            return "Нет активного воспроизведения"
        return self.active_provider.pause()

    def resume(self) -> str:
        """Resume active provider playback."""
        if self.active_provider is None:
            return "Нет активного воспроизведения"
        return self.active_provider.resume()

    def fullscreen(self) -> str:
        """Toggle fullscreen on active provider."""
        if self.active_provider is None:
            return "Нет активного воспроизведения"
        return self.active_provider.fullscreen()
