"""Tests for RegexIntentRouter."""

import pytest

from media_assistant.intents.types import Intent, IntentType
from media_assistant.intents.regex_router import RegexIntentRouter


@pytest.fixture
def router():
    return RegexIntentRouter()


class TestPlayMediaIntent:
    def test_включи(self, router):
        intent = router.route("включи интерстеллар")
        assert intent.type == IntentType.PLAY_MEDIA
        assert intent.query == "интерстеллар"

    def test_поставь(self, router):
        intent = router.route("поставь музыку")
        assert intent.type == IntentType.PLAY_MEDIA
        assert intent.query == "музыку"

    def test_запусти(self, router):
        intent = router.route("запусти рок")
        assert intent.type == IntentType.PLAY_MEDIA
        assert intent.query == "рок"


class TestPauseIntent:
    def test_пауза(self, router):
        assert router.route("пауза").type == IntentType.PAUSE

    def test_стоп(self, router):
        assert router.route("стоп").type == IntentType.PAUSE

    def test_останови(self, router):
        assert router.route("останови").type == IntentType.PAUSE


class TestResumeIntent:
    def test_продолжи(self, router):
        assert router.route("продолжи").type == IntentType.RESUME

    def test_играй(self, router):
        assert router.route("играй").type == IntentType.RESUME

    def test_play(self, router):
        assert router.route("play").type == IntentType.RESUME


class TestVolumeIntents:
    def test_громче(self, router):
        assert router.route("громче").type == IntentType.VOLUME_UP

    def test_прибавь_звук(self, router):
        assert router.route("прибавь звук").type == IntentType.VOLUME_UP

    def test_тише(self, router):
        assert router.route("тише").type == IntentType.VOLUME_DOWN

    def test_убавь_звук(self, router):
        assert router.route("убавь звук").type == IntentType.VOLUME_DOWN

    def test_громкость_50(self, router):
        intent = router.route("громкость 50")
        assert intent.type == IntentType.VOLUME_SET
        assert intent.params["level"] == 50

    def test_громкость_0(self, router):
        intent = router.route("громкость 0")
        assert intent.type == IntentType.VOLUME_SET
        assert intent.params["level"] == 0


class TestSystemIntents:
    def test_выключи_компьютер(self, router):
        assert router.route("выключи компьютер").type == IntentType.SHUTDOWN

    def test_перезагрузи(self, router):
        assert router.route("перезагрузи").type == IntentType.REBOOT

    def test_перезагрузка(self, router):
        assert router.route("перезагрузка").type == IntentType.REBOOT


class TestMediaControlIntents:
    def test_fullscreen(self, router):
        assert router.route("на весь экран").type == IntentType.FULLSCREEN

    def test_фулскрин(self, router):
        assert router.route("фулскрин").type == IntentType.FULLSCREEN

    def test_закрой(self, router):
        assert router.route("закрой").type == IntentType.CLOSE

    def test_следующий(self, router):
        assert router.route("следующий").type == IntentType.NEXT_TRACK

    def test_дальше(self, router):
        assert router.route("дальше").type == IntentType.NEXT_TRACK

    def test_предыдущий(self, router):
        assert router.route("предыдущий").type == IntentType.PREV_TRACK

    def test_назад(self, router):
        assert router.route("назад").type == IntentType.PREV_TRACK


class TestUnknownIntent:
    def test_unknown(self, router):
        intent = router.route("какая погода")
        assert intent.type == IntentType.UNKNOWN
        assert intent.query == "какая погода"


class TestCaseInsensitivity:
    def test_uppercase(self, router):
        assert router.route("ПАУЗА").type == IntentType.PAUSE

    def test_mixed_case(self, router):
        intent = router.route("Включи Музыку")
        assert intent.type == IntentType.PLAY_MEDIA
        assert intent.query == "музыку"


class TestWhitespaceHandling:
    def test_leading_trailing_spaces(self, router):
        assert router.route("  пауза  ").type == IntentType.PAUSE
