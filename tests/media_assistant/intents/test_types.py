"""Tests for Intent types."""

from media_assistant.intents.types import Intent, IntentType


class TestIntentType:
    def test_all_intent_types_exist(self):
        """All expected intent types should be defined."""
        expected = [
            "PLAY_MEDIA", "PAUSE", "RESUME", "VOLUME_UP", "VOLUME_DOWN",
            "VOLUME_SET", "SHUTDOWN", "REBOOT", "FULLSCREEN", "CLOSE",
            "NEXT_TRACK", "PREV_TRACK", "UNKNOWN",
        ]
        for name in expected:
            assert hasattr(IntentType, name)


class TestIntent:
    def test_intent_defaults(self):
        """Intent should have sensible defaults."""
        intent = Intent(type=IntentType.PAUSE)
        assert intent.type == IntentType.PAUSE
        assert intent.query == ""
        assert intent.params == {}

    def test_intent_with_query(self):
        intent = Intent(type=IntentType.PLAY_MEDIA, query="интерстеллар")
        assert intent.query == "интерстеллар"

    def test_intent_with_params(self):
        intent = Intent(type=IntentType.VOLUME_SET, params={"level": 50})
        assert intent.params["level"] == 50
