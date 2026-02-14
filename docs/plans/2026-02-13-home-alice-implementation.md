# Home Alice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Voice-control a Windows PC via Yandex Alice — search and play VK Video, shutdown/reboot the computer.

**Architecture:** VPS runs a FastAPI server that receives webhooks from Yandex Dialogs, parses commands via YandexGPT, searches VK Video API, and sends actions to the home PC over WebSocket. The Windows PC runs an agent that maintains a persistent WebSocket connection and executes commands locally.

**Tech Stack:** Python 3.11+, FastAPI, websockets, httpx, pydantic, pyyaml, pytest, pytest-asyncio

---

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `server/requirements.txt`
- Create: `server/config.example.yaml`
- Create: `agent/requirements.txt`
- Create: `agent/config.example.yaml`
- Create: `server/__init__.py`
- Create: `agent/__init__.py`
- Create: `agent/commands/__init__.py`

**Step 1: Create server directory and requirements**

```
server/requirements.txt:
```
```
fastapi==0.115.6
uvicorn==0.34.0
websockets==14.1
httpx==0.28.1
pydantic==2.10.4
pyyaml==6.0.2
```

**Step 2: Create server config example**

```
server/config.example.yaml:
```
```yaml
api_key: "your-secret-agent-key"
vk_token: "your-vk-api-token"
yandex_gpt_api_key: "your-yandexgpt-api-key"
yandex_gpt_folder_id: "your-yandex-cloud-folder-id"
favorite_channels:
  # "channel-name": -group_id
```

**Step 3: Create agent directory and requirements**

```
agent/requirements.txt:
```
```
websockets==14.1
pyyaml==6.0.2
```

**Step 4: Create agent config example**

```
agent/config.example.yaml:
```
```yaml
server_url: "wss://your-vps.com/ws/agent"
api_key: "your-secret-agent-key"
allowed_domains:
  - "vk.com"
  - "youtube.com"
```

**Step 5: Create `__init__.py` files**

Empty files for: `server/__init__.py`, `agent/__init__.py`, `agent/commands/__init__.py`

**Step 6: Create dev requirements for testing**

```
requirements-dev.txt:
```
```
pytest==8.3.4
pytest-asyncio==0.25.0
httpx==0.28.1
respx==0.22.0
```

**Step 7: Commit**

```bash
git add server/ agent/ requirements-dev.txt
git commit -m "chore: scaffold project structure and dependencies"
```

---

### Task 2: Server config module

**Files:**
- Create: `server/config.py`
- Create: `tests/server/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/server/test_config.py`

**Step 1: Write the failing test**

```python
# tests/server/test_config.py
import os
import tempfile
import yaml
import pytest
from server.config import load_config, ServerConfig


def test_load_config_from_file():
    data = {
        "api_key": "test-key",
        "vk_token": "vk-token-123",
        "yandex_gpt_api_key": "gpt-key-456",
        "yandex_gpt_folder_id": "folder-789",
        "favorite_channels": {"testchannel": -123456},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        path = f.name
    try:
        config = load_config(path)
        assert isinstance(config, ServerConfig)
        assert config.api_key == "test-key"
        assert config.vk_token == "vk-token-123"
        assert config.yandex_gpt_api_key == "gpt-key-456"
        assert config.yandex_gpt_folder_id == "folder-789"
        assert config.favorite_channels == {"testchannel": -123456}
    finally:
        os.unlink(path)


def test_load_config_missing_field():
    data = {"api_key": "test-key"}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        path = f.name
    try:
        with pytest.raises(Exception):
            load_config(path)
    finally:
        os.unlink(path)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'server.config'"

**Step 3: Write minimal implementation**

```python
# server/config.py
from dataclasses import dataclass
import yaml


@dataclass
class ServerConfig:
    api_key: str
    vk_token: str
    yandex_gpt_api_key: str
    yandex_gpt_folder_id: str
    favorite_channels: dict[str, int]


def load_config(path: str) -> ServerConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return ServerConfig(
        api_key=data["api_key"],
        vk_token=data["vk_token"],
        yandex_gpt_api_key=data["yandex_gpt_api_key"],
        yandex_gpt_folder_id=data["yandex_gpt_folder_id"],
        favorite_channels=data.get("favorite_channels", {}),
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/server/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/config.py tests/
git commit -m "feat(server): add config module with YAML loading"
```

---

### Task 3: Command protocol (shared data models)

**Files:**
- Create: `server/models.py`
- Create: `tests/server/test_models.py`

**Step 1: Write the failing test**

```python
# tests/server/test_models.py
import json
from server.models import Command, CommandResult


def test_command_serialization():
    cmd = Command(action="open_url", params={"url": "https://vk.com/video123"})
    data = cmd.to_json()
    parsed = json.loads(data)
    assert parsed["action"] == "open_url"
    assert parsed["params"]["url"] == "https://vk.com/video123"


def test_command_deserialization():
    raw = '{"action": "shutdown", "params": {}}'
    cmd = Command.from_json(raw)
    assert cmd.action == "shutdown"
    assert cmd.params == {}


def test_command_result_serialization():
    result = CommandResult(success=True, message="Done")
    data = result.to_json()
    parsed = json.loads(data)
    assert parsed["success"] is True
    assert parsed["message"] == "Done"


def test_unknown_action():
    cmd = Command(action="unknown", params={})
    assert cmd.action == "unknown"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# server/models.py
import json
from dataclasses import dataclass, field, asdict


@dataclass
class Command:
    action: str
    params: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "Command":
        data = json.loads(raw)
        return cls(action=data["action"], params=data.get("params", {}))


@dataclass
class CommandResult:
    success: bool
    message: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "CommandResult":
        data = json.loads(raw)
        return cls(success=data["success"], message=data.get("message", ""))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/server/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/models.py tests/server/test_models.py
git commit -m "feat: add Command and CommandResult data models"
```

---

### Task 4: YandexGPT command parser

**Files:**
- Create: `server/command_parser.py`
- Create: `tests/server/test_command_parser.py`

**Step 1: Write the failing test**

We mock the HTTP call to YandexGPT API. The parser should send user text to YandexGPT and parse the JSON response into a Command.

```python
# tests/server/test_command_parser.py
import json
import pytest
import httpx
import respx
from server.command_parser import CommandParser
from server.models import Command

YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


@pytest.fixture
def parser():
    return CommandParser(
        api_key="test-api-key",
        folder_id="test-folder-id",
    )


@respx.mock
@pytest.mark.asyncio
async def test_parse_shutdown_command(parser):
    gpt_response = {
        "result": {
            "alternatives": [
                {
                    "message": {
                        "role": "assistant",
                        "text": '{"action": "shutdown", "params": {}}',
                    },
                    "status": "ALTERNATIVE_STATUS_FINAL",
                }
            ],
            "usage": {"inputTextTokens": "50", "completionTokens": "10", "totalTokens": "60"},
        }
    }
    respx.post(YANDEX_GPT_URL).mock(return_value=httpx.Response(200, json=gpt_response))

    cmd = await parser.parse("выключи компьютер")
    assert cmd.action == "shutdown"
    assert cmd.params == {}


@respx.mock
@pytest.mark.asyncio
async def test_parse_vk_video_command(parser):
    gpt_response = {
        "result": {
            "alternatives": [
                {
                    "message": {
                        "role": "assistant",
                        "text": '{"action": "open_vk_video", "params": {"query": "смешные коты"}}',
                    },
                    "status": "ALTERNATIVE_STATUS_FINAL",
                }
            ],
            "usage": {"inputTextTokens": "50", "completionTokens": "20", "totalTokens": "70"},
        }
    }
    respx.post(YANDEX_GPT_URL).mock(return_value=httpx.Response(200, json=gpt_response))

    cmd = await parser.parse("покажи смешных котиков")
    assert cmd.action == "open_vk_video"
    assert cmd.params["query"] == "смешные коты"


@respx.mock
@pytest.mark.asyncio
async def test_parse_unknown_command(parser):
    gpt_response = {
        "result": {
            "alternatives": [
                {
                    "message": {
                        "role": "assistant",
                        "text": '{"action": "unknown"}',
                    },
                    "status": "ALTERNATIVE_STATUS_FINAL",
                }
            ],
            "usage": {"inputTextTokens": "50", "completionTokens": "5", "totalTokens": "55"},
        }
    }
    respx.post(YANDEX_GPT_URL).mock(return_value=httpx.Response(200, json=gpt_response))

    cmd = await parser.parse("какая погода")
    assert cmd.action == "unknown"


@respx.mock
@pytest.mark.asyncio
async def test_parse_handles_api_error(parser):
    respx.post(YANDEX_GPT_URL).mock(return_value=httpx.Response(500, text="Internal Server Error"))

    cmd = await parser.parse("выключи компьютер")
    assert cmd.action == "unknown"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_command_parser.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# server/command_parser.py
import json
import logging
import httpx
from server.models import Command

logger = logging.getLogger(__name__)

YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

SYSTEM_PROMPT = """Ты — парсер голосовых команд для управления домашним ПК.
Доступные действия:
- shutdown: выключить компьютер
- reboot: перезагрузить компьютер
- open_vk_video: найти и открыть видео на VK Video (параметры: query — поисковый запрос, channel — название канала если указано)
- open_url: открыть произвольный URL в браузере (параметры: url)

Верни ТОЛЬКО валидный JSON без markdown-разметки: {"action": "...", "params": {...}}
Если команда не распознана — {"action": "unknown"}"""


class CommandParser:
    def __init__(self, api_key: str, folder_id: str):
        self.api_key = api_key
        self.folder_id = folder_id

    async def parse(self, text: str) -> Command:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    YANDEX_GPT_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Api-Key {self.api_key}",
                    },
                    json={
                        "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite/latest",
                        "completionOptions": {
                            "stream": False,
                            "temperature": 0.1,
                            "maxTokens": 200,
                        },
                        "messages": [
                            {"role": "system", "text": SYSTEM_PROMPT},
                            {"role": "user", "text": text},
                        ],
                    },
                    timeout=4.0,
                )
                response.raise_for_status()
                data = response.json()
                raw_text = data["result"]["alternatives"][0]["message"]["text"]
                parsed = json.loads(raw_text)
                return Command(
                    action=parsed.get("action", "unknown"),
                    params=parsed.get("params", {}),
                )
        except Exception as e:
            logger.error("Failed to parse command: %s", e)
            return Command(action="unknown")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/server/test_command_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/command_parser.py tests/server/test_command_parser.py
git commit -m "feat(server): add YandexGPT command parser"
```

---

### Task 5: VK Video search module

**Files:**
- Create: `server/vk_video.py`
- Create: `tests/server/test_vk_video.py`

**Step 1: Write the failing test**

```python
# tests/server/test_vk_video.py
import pytest
import httpx
import respx
from server.vk_video import VKVideoSearch

VK_API_URL = "https://api.vk.com/method/video.search"


@pytest.fixture
def vk():
    return VKVideoSearch(token="test-vk-token", favorite_channels={"testchannel": -123456})


@respx.mock
@pytest.mark.asyncio
async def test_search_returns_most_viewed(vk):
    vk_response = {
        "response": {
            "count": 2,
            "items": [
                {"id": 111, "owner_id": -100, "title": "Low views", "views": 50},
                {"id": 222, "owner_id": -200, "title": "High views", "views": 5000},
            ],
        }
    }
    respx.get(VK_API_URL).mock(return_value=httpx.Response(200, json=vk_response))

    url = await vk.search("котики")
    # Should return the most viewed video
    assert url == "https://vk.com/video-200_222"


@respx.mock
@pytest.mark.asyncio
async def test_search_with_channel(vk):
    vk_response = {
        "response": {
            "count": 1,
            "items": [
                {"id": 333, "owner_id": -123456, "title": "Channel video", "views": 100},
            ],
        }
    }
    route = respx.get(VK_API_URL).mock(return_value=httpx.Response(200, json=vk_response))

    url = await vk.search("котики", channel="testchannel")
    assert url == "https://vk.com/video-123456_333"
    # Verify owner_id was passed
    request = route.calls[0].request
    assert "owner_id=-123456" in str(request.url)


@respx.mock
@pytest.mark.asyncio
async def test_search_no_results(vk):
    vk_response = {"response": {"count": 0, "items": []}}
    respx.get(VK_API_URL).mock(return_value=httpx.Response(200, json=vk_response))

    url = await vk.search("несуществующее видео абвгд")
    assert url is None


@respx.mock
@pytest.mark.asyncio
async def test_search_api_error(vk):
    respx.get(VK_API_URL).mock(return_value=httpx.Response(500, text="Error"))

    url = await vk.search("котики")
    assert url is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_vk_video.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# server/vk_video.py
import logging
import httpx

logger = logging.getLogger(__name__)

VK_API_URL = "https://api.vk.com/method/video.search"
VK_API_VERSION = "5.199"


class VKVideoSearch:
    def __init__(self, token: str, favorite_channels: dict[str, int] | None = None):
        self.token = token
        self.favorite_channels = favorite_channels or {}

    async def search(self, query: str, channel: str | None = None) -> str | None:
        params = {
            "q": query,
            "access_token": self.token,
            "v": VK_API_VERSION,
            "count": 10,
            "sort": 2,  # by relevance
        }
        if channel and channel in self.favorite_channels:
            params["owner_id"] = self.favorite_channels[channel]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(VK_API_URL, params=params, timeout=4.0)
                response.raise_for_status()
                data = response.json()

            items = data.get("response", {}).get("items", [])
            if not items:
                return None

            # Pick the most viewed video from results
            best = max(items, key=lambda v: v.get("views", 0))
            owner_id = best["owner_id"]
            video_id = best["id"]
            return f"https://vk.com/video{owner_id}_{video_id}"

        except Exception as e:
            logger.error("VK video search failed: %s", e)
            return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/server/test_vk_video.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/vk_video.py tests/server/test_vk_video.py
git commit -m "feat(server): add VK Video search with most-viewed sorting"
```

---

### Task 6: WebSocket agent manager

**Files:**
- Create: `server/agent_manager.py`
- Create: `tests/server/test_agent_manager.py`

**Step 1: Write the failing test**

The AgentManager tracks one connected agent and sends/receives commands.

```python
# tests/server/test_agent_manager.py
import asyncio
import pytest
from server.agent_manager import AgentManager
from server.models import Command, CommandResult


@pytest.mark.asyncio
async def test_no_agent_connected():
    manager = AgentManager()
    result = await manager.send_command(Command(action="shutdown"))
    assert result is None


@pytest.mark.asyncio
async def test_agent_connected_flag():
    manager = AgentManager()
    assert manager.is_connected is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_agent_manager.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# server/agent_manager.py
import asyncio
import json
import logging
from server.models import Command, CommandResult

logger = logging.getLogger(__name__)


class AgentManager:
    def __init__(self):
        self._ws = None
        self._response_event: asyncio.Event | None = None
        self._response_data: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._ws is not None

    def register(self, ws) -> None:
        self._ws = ws
        logger.info("PC agent connected")

    def unregister(self) -> None:
        self._ws = None
        logger.info("PC agent disconnected")

    async def send_command(self, command: Command, timeout: float = 5.0) -> CommandResult | None:
        if not self._ws:
            return None
        try:
            self._response_event = asyncio.Event()
            self._response_data = None
            await self._ws.send_text(command.to_json())
            await asyncio.wait_for(self._response_event.wait(), timeout=timeout)
            if self._response_data:
                return CommandResult.from_json(self._response_data)
            return None
        except asyncio.TimeoutError:
            logger.warning("Agent did not respond within %s seconds", timeout)
            return None
        except Exception as e:
            logger.error("Failed to send command to agent: %s", e)
            return None
        finally:
            self._response_event = None

    def receive_response(self, data: str) -> None:
        self._response_data = data
        if self._response_event:
            self._response_event.set()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/server/test_agent_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/agent_manager.py tests/server/test_agent_manager.py
git commit -m "feat(server): add WebSocket agent manager"
```

---

### Task 7: Alice webhook handler

**Files:**
- Create: `server/alice_handler.py`
- Create: `tests/server/test_alice_handler.py`

**Step 1: Write the failing test**

```python
# tests/server/test_alice_handler.py
import pytest
from server.alice_handler import AliceHandler
from server.models import Command, CommandResult
from server.agent_manager import AgentManager


class FakeParser:
    def __init__(self, command: Command):
        self._command = command

    async def parse(self, text: str) -> Command:
        return self._command


class FakeVKVideo:
    def __init__(self, url: str | None):
        self._url = url

    async def search(self, query: str, channel: str | None = None) -> str | None:
        return self._url


class FakeAgentManager:
    def __init__(self, result: CommandResult | None):
        self._result = result
        self.is_connected = result is not None

    async def send_command(self, command, timeout=5.0):
        return self._result


@pytest.mark.asyncio
async def test_handle_ping():
    handler = AliceHandler(
        parser=FakeParser(Command(action="unknown")),
        vk_video=FakeVKVideo(None),
        agent=FakeAgentManager(None),
    )
    request = {
        "request": {"command": "", "original_utterance": "ping", "type": "SimpleUtterance"},
        "session": {"new": True, "session_id": "123", "message_id": 0, "skill_id": "test"},
        "version": "1.0",
    }
    response = await handler.handle(request)
    assert response["version"] == "1.0"
    assert response["response"]["text"] == "pong"


@pytest.mark.asyncio
async def test_handle_shutdown():
    handler = AliceHandler(
        parser=FakeParser(Command(action="shutdown")),
        vk_video=FakeVKVideo(None),
        agent=FakeAgentManager(CommandResult(success=True, message="OK")),
    )
    request = {
        "request": {"command": "выключи компьютер", "original_utterance": "Выключи компьютер", "type": "SimpleUtterance"},
        "session": {"new": False, "session_id": "123", "message_id": 1, "skill_id": "test"},
        "version": "1.0",
    }
    response = await handler.handle(request)
    assert "выключаю" in response["response"]["text"].lower()


@pytest.mark.asyncio
async def test_handle_vk_video():
    handler = AliceHandler(
        parser=FakeParser(Command(action="open_vk_video", params={"query": "смешные коты"})),
        vk_video=FakeVKVideo("https://vk.com/video-123_456"),
        agent=FakeAgentManager(CommandResult(success=True, message="Opened")),
    )
    request = {
        "request": {"command": "покажи смешных котиков", "original_utterance": "Покажи смешных котиков", "type": "SimpleUtterance"},
        "session": {"new": False, "session_id": "123", "message_id": 1, "skill_id": "test"},
        "version": "1.0",
    }
    response = await handler.handle(request)
    assert "видео" in response["response"]["text"].lower() or "включаю" in response["response"]["text"].lower()


@pytest.mark.asyncio
async def test_handle_agent_offline():
    handler = AliceHandler(
        parser=FakeParser(Command(action="shutdown")),
        vk_video=FakeVKVideo(None),
        agent=FakeAgentManager(None),
    )
    handler.agent.is_connected = False  # type: ignore
    request = {
        "request": {"command": "выключи компьютер", "original_utterance": "Выключи компьютер", "type": "SimpleUtterance"},
        "session": {"new": False, "session_id": "123", "message_id": 1, "skill_id": "test"},
        "version": "1.0",
    }
    response = await handler.handle(request)
    assert "недоступен" in response["response"]["text"].lower()


@pytest.mark.asyncio
async def test_handle_unknown_command():
    handler = AliceHandler(
        parser=FakeParser(Command(action="unknown")),
        vk_video=FakeVKVideo(None),
        agent=FakeAgentManager(CommandResult(success=True)),
    )
    request = {
        "request": {"command": "какая погода", "original_utterance": "Какая погода", "type": "SimpleUtterance"},
        "session": {"new": False, "session_id": "123", "message_id": 1, "skill_id": "test"},
        "version": "1.0",
    }
    response = await handler.handle(request)
    assert "не поняла" in response["response"]["text"].lower()


@pytest.mark.asyncio
async def test_handle_vk_video_not_found():
    handler = AliceHandler(
        parser=FakeParser(Command(action="open_vk_video", params={"query": "абвгд"})),
        vk_video=FakeVKVideo(None),  # No results
        agent=FakeAgentManager(CommandResult(success=True)),
    )
    request = {
        "request": {"command": "найди абвгд", "original_utterance": "Найди абвгд", "type": "SimpleUtterance"},
        "session": {"new": False, "session_id": "123", "message_id": 1, "skill_id": "test"},
        "version": "1.0",
    }
    response = await handler.handle(request)
    assert "не нашла" in response["response"]["text"].lower()


@pytest.mark.asyncio
async def test_handle_new_session_greeting():
    handler = AliceHandler(
        parser=FakeParser(Command(action="unknown")),
        vk_video=FakeVKVideo(None),
        agent=FakeAgentManager(None),
    )
    request = {
        "request": {"command": "", "original_utterance": "", "type": "SimpleUtterance"},
        "session": {"new": True, "session_id": "123", "message_id": 0, "skill_id": "test"},
        "version": "1.0",
    }
    response = await handler.handle(request)
    assert response["response"]["end_session"] is False
    assert len(response["response"]["text"]) > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_alice_handler.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# server/alice_handler.py
import logging
from server.models import Command

logger = logging.getLogger(__name__)

GREETING = (
    "Привет! Я могу управлять твоим компьютером. "
    "Скажи, например: «выключи компьютер» или «покажи смешных котиков»."
)


class AliceHandler:
    def __init__(self, parser, vk_video, agent):
        self.parser = parser
        self.vk_video = vk_video
        self.agent = agent

    async def handle(self, request: dict) -> dict:
        utterance = request.get("request", {}).get("original_utterance", "")
        command_text = request.get("request", {}).get("command", "")
        is_new = request.get("session", {}).get("new", False)
        version = request.get("version", "1.0")

        # Health check
        if utterance == "ping":
            return self._response("pong", end_session=False, version=version)

        # New session greeting
        if is_new and not command_text:
            return self._response(GREETING, end_session=False, version=version)

        # Parse command via YandexGPT
        cmd = await self.parser.parse(command_text)

        if cmd.action == "unknown":
            return self._response(
                "Не поняла команду. Попробуй сказать иначе.",
                end_session=False,
                version=version,
            )

        # Check agent connectivity for PC commands
        if cmd.action in ("shutdown", "reboot", "open_url") and not self.agent.is_connected:
            return self._response(
                "Компьютер сейчас недоступен.",
                end_session=False,
                version=version,
            )

        # Handle VK video search
        if cmd.action == "open_vk_video":
            query = cmd.params.get("query", command_text)
            channel = cmd.params.get("channel")
            url = await self.vk_video.search(query, channel=channel)
            if not url:
                return self._response(
                    f"Не нашла видео по запросу «{query}».",
                    end_session=False,
                    version=version,
                )
            if not self.agent.is_connected:
                return self._response(
                    "Компьютер сейчас недоступен.",
                    end_session=False,
                    version=version,
                )
            open_cmd = Command(action="open_url", params={"url": url})
            result = await self.agent.send_command(open_cmd)
            if result and result.success:
                return self._response(
                    f"Включаю видео по запросу «{query}».",
                    end_session=False,
                    version=version,
                )
            return self._response(
                "Команда отправлена, но компьютер не ответил.",
                end_session=False,
                version=version,
            )

        # Handle shutdown/reboot
        if cmd.action in ("shutdown", "reboot"):
            result = await self.agent.send_command(cmd)
            if result and result.success:
                action_text = "Выключаю" if cmd.action == "shutdown" else "Перезагружаю"
                return self._response(
                    f"{action_text} компьютер.",
                    end_session=False,
                    version=version,
                )
            return self._response(
                "Команда отправлена, но компьютер не ответил.",
                end_session=False,
                version=version,
            )

        # Handle open_url
        if cmd.action == "open_url":
            result = await self.agent.send_command(cmd)
            if result and result.success:
                return self._response(
                    "Открываю ссылку.",
                    end_session=False,
                    version=version,
                )
            return self._response(
                "Команда отправлена, но компьютер не ответил.",
                end_session=False,
                version=version,
            )

        return self._response(
            "Не поняла команду. Попробуй сказать иначе.",
            end_session=False,
            version=version,
        )

    @staticmethod
    def _response(text: str, end_session: bool, version: str) -> dict:
        return {
            "response": {
                "text": text,
                "end_session": end_session,
            },
            "version": version,
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/server/test_alice_handler.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/alice_handler.py tests/server/test_alice_handler.py
git commit -m "feat(server): add Alice webhook handler with all command flows"
```

---

### Task 8: Server main.py — FastAPI app

**Files:**
- Create: `server/main.py`
- Create: `tests/server/test_main.py`

**Step 1: Write the failing test**

Test the FastAPI app using `httpx.AsyncClient` with `ASGITransport`.

```python
# tests/server/test_main.py
import os
import tempfile
import yaml
import pytest
import httpx
from httpx import ASGITransport


@pytest.fixture
def config_path():
    data = {
        "api_key": "test-agent-key",
        "vk_token": "test-vk-token",
        "yandex_gpt_api_key": "test-gpt-key",
        "yandex_gpt_folder_id": "test-folder",
        "favorite_channels": {},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def app(config_path):
    os.environ["CONFIG_PATH"] = config_path
    # Re-import to pick up env var
    import importlib
    import server.main
    importlib.reload(server.main)
    return server.main.app


@pytest.mark.asyncio
async def test_health_endpoint(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_alice_webhook_ping(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        request_body = {
            "request": {"command": "", "original_utterance": "ping", "type": "SimpleUtterance"},
            "session": {"new": True, "session_id": "123", "message_id": 0, "skill_id": "test"},
            "version": "1.0",
        }
        response = await client.post("/alice/webhook", json=request_body)
        assert response.status_code == 200
        assert response.json()["response"]["text"] == "pong"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_main.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# server/main.py
import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
from server.config import load_config
from server.command_parser import CommandParser
from server.vk_video import VKVideoSearch
from server.agent_manager import AgentManager
from server.alice_handler import AliceHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config_path = os.environ.get("CONFIG_PATH", "server/config.yaml")
config = load_config(config_path)

parser = CommandParser(api_key=config.yandex_gpt_api_key, folder_id=config.yandex_gpt_folder_id)
vk_video = VKVideoSearch(token=config.vk_token, favorite_channels=config.favorite_channels)
agent_manager = AgentManager()
alice_handler = AliceHandler(parser=parser, vk_video=vk_video, agent=agent_manager)

app = FastAPI(title="Home Alice Server")


@app.get("/health")
async def health():
    return {"status": "ok", "agent_connected": agent_manager.is_connected}


@app.post("/alice/webhook")
async def alice_webhook(request: Request):
    body = await request.json()
    response = await alice_handler.handle(body)
    return JSONResponse(content=response)


@app.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket):
    # Check API key from query param
    key = websocket.query_params.get("key", "")
    if key != config.api_key:
        await websocket.close(code=4001, reason="Invalid API key")
        return

    await websocket.accept()
    agent_manager.register(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            agent_manager.receive_response(data)
    except WebSocketDisconnect:
        agent_manager.unregister()
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        agent_manager.unregister()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/server/test_main.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/main.py tests/server/test_main.py
git commit -m "feat(server): add FastAPI main app with webhook and WebSocket endpoints"
```

---

### Task 9: Agent — system commands (shutdown, reboot)

**Files:**
- Create: `agent/commands/system.py`
- Create: `tests/agent/__init__.py`
- Create: `tests/agent/commands/__init__.py`
- Create: `tests/agent/commands/test_system.py`

**Step 1: Write the failing test**

We mock `subprocess.run` to avoid actually shutting down the machine.

```python
# tests/agent/commands/test_system.py
from unittest.mock import patch, MagicMock
from agent.commands.system import shutdown, reboot


@patch("agent.commands.system.subprocess.run")
def test_shutdown(mock_run):
    result = shutdown()
    mock_run.assert_called_once_with(["shutdown", "/s", "/t", "0"], check=True)
    assert result.success is True


@patch("agent.commands.system.subprocess.run")
def test_reboot(mock_run):
    result = reboot()
    mock_run.assert_called_once_with(["shutdown", "/r", "/t", "0"], check=True)
    assert result.success is True


@patch("agent.commands.system.subprocess.run", side_effect=Exception("Permission denied"))
def test_shutdown_failure(mock_run):
    result = shutdown()
    assert result.success is False
    assert "Permission denied" in result.message
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/commands/test_system.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# agent/commands/system.py
import subprocess
import logging
from server.models import CommandResult

logger = logging.getLogger(__name__)


def shutdown() -> CommandResult:
    try:
        subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
        return CommandResult(success=True, message="Shutdown initiated")
    except Exception as e:
        logger.error("Shutdown failed: %s", e)
        return CommandResult(success=False, message=str(e))


def reboot() -> CommandResult:
    try:
        subprocess.run(["shutdown", "/r", "/t", "0"], check=True)
        return CommandResult(success=True, message="Reboot initiated")
    except Exception as e:
        logger.error("Reboot failed: %s", e)
        return CommandResult(success=False, message=str(e))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/commands/test_system.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agent/commands/system.py tests/agent/
git commit -m "feat(agent): add shutdown and reboot commands"
```

---

### Task 10: Agent — browser commands (open_url with domain whitelist)

**Files:**
- Create: `agent/commands/browser.py`
- Create: `tests/agent/commands/test_browser.py`

**Step 1: Write the failing test**

```python
# tests/agent/commands/test_browser.py
from unittest.mock import patch
from agent.commands.browser import open_url
from server.models import CommandResult


ALLOWED = ["vk.com", "youtube.com"]


@patch("agent.commands.browser.webbrowser.open")
def test_open_allowed_url(mock_open):
    result = open_url("https://vk.com/video-123_456", ALLOWED)
    mock_open.assert_called_once_with("https://vk.com/video-123_456")
    assert result.success is True


@patch("agent.commands.browser.webbrowser.open")
def test_open_blocked_url(mock_open):
    result = open_url("https://evil.com/malware", ALLOWED)
    mock_open.assert_not_called()
    assert result.success is False
    assert "запрещён" in result.message.lower() or "blocked" in result.message.lower()


@patch("agent.commands.browser.webbrowser.open")
def test_open_subdomain_allowed(mock_open):
    result = open_url("https://m.vk.com/video123", ALLOWED)
    mock_open.assert_called_once()
    assert result.success is True


@patch("agent.commands.browser.webbrowser.open", side_effect=Exception("No browser"))
def test_open_url_failure(mock_open):
    result = open_url("https://vk.com/video123", ALLOWED)
    assert result.success is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/commands/test_browser.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# agent/commands/browser.py
import webbrowser
import logging
from urllib.parse import urlparse
from server.models import CommandResult

logger = logging.getLogger(__name__)


def open_url(url: str, allowed_domains: list[str]) -> CommandResult:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if not any(hostname == d or hostname.endswith(f".{d}") for d in allowed_domains):
            return CommandResult(success=False, message=f"Домен {hostname} запрещён")
        webbrowser.open(url)
        return CommandResult(success=True, message=f"Opened {url}")
    except Exception as e:
        logger.error("Failed to open URL: %s", e)
        return CommandResult(success=False, message=str(e))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/commands/test_browser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agent/commands/browser.py tests/agent/commands/test_browser.py
git commit -m "feat(agent): add URL opener with domain whitelist"
```

---

### Task 11: Agent — config module

**Files:**
- Create: `agent/config.py`
- Create: `tests/agent/test_config.py`

**Step 1: Write the failing test**

```python
# tests/agent/test_config.py
import os
import tempfile
import yaml
import pytest
from agent.config import load_agent_config, AgentConfig


def test_load_agent_config():
    data = {
        "server_url": "wss://example.com/ws/agent",
        "api_key": "test-key",
        "allowed_domains": ["vk.com", "youtube.com"],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        path = f.name
    try:
        config = load_agent_config(path)
        assert isinstance(config, AgentConfig)
        assert config.server_url == "wss://example.com/ws/agent"
        assert config.api_key == "test-key"
        assert "vk.com" in config.allowed_domains
    finally:
        os.unlink(path)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_config.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# agent/config.py
from dataclasses import dataclass, field
import yaml


@dataclass
class AgentConfig:
    server_url: str
    api_key: str
    allowed_domains: list[str] = field(default_factory=list)


def load_agent_config(path: str) -> AgentConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return AgentConfig(
        server_url=data["server_url"],
        api_key=data["api_key"],
        allowed_domains=data.get("allowed_domains", []),
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agent/config.py tests/agent/test_config.py
git commit -m "feat(agent): add config module"
```

---

### Task 12: Agent — main.py (WebSocket client + command dispatcher)

**Files:**
- Create: `agent/main.py`
- Create: `tests/agent/test_main.py`

**Step 1: Write the failing test**

Test the command dispatcher logic separately from the WebSocket connection.

```python
# tests/agent/test_main.py
from unittest.mock import patch
import pytest
from agent.main import dispatch_command
from server.models import Command


@patch("agent.commands.system.subprocess.run")
def test_dispatch_shutdown(mock_run):
    result = dispatch_command(Command(action="shutdown"), allowed_domains=["vk.com"])
    assert result.success is True
    mock_run.assert_called_once()


@patch("agent.commands.browser.webbrowser.open")
def test_dispatch_open_url(mock_open):
    result = dispatch_command(
        Command(action="open_url", params={"url": "https://vk.com/video123"}),
        allowed_domains=["vk.com"],
    )
    assert result.success is True


def test_dispatch_unknown_action():
    result = dispatch_command(Command(action="fly_to_moon"), allowed_domains=[])
    assert result.success is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_main.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# agent/main.py
import asyncio
import logging
import os
import websockets
from server.models import Command, CommandResult
from agent.config import load_agent_config
from agent.commands.system import shutdown, reboot
from agent.commands.browser import open_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def dispatch_command(command: Command, allowed_domains: list[str]) -> CommandResult:
    if command.action == "shutdown":
        return shutdown()
    elif command.action == "reboot":
        return reboot()
    elif command.action == "open_url":
        url = command.params.get("url", "")
        return open_url(url, allowed_domains)
    else:
        return CommandResult(success=False, message=f"Unknown action: {command.action}")


async def run_agent(config_path: str):
    config = load_agent_config(config_path)
    url = f"{config.server_url}?key={config.api_key}"

    while True:
        try:
            logger.info("Connecting to %s", config.server_url)
            async with websockets.connect(url) as ws:
                logger.info("Connected to server")
                async for message in ws:
                    try:
                        cmd = Command.from_json(message)
                        logger.info("Received command: %s", cmd.action)
                        result = dispatch_command(cmd, config.allowed_domains)
                        await ws.send(result.to_json())
                        logger.info("Command result: %s", result.success)
                    except Exception as e:
                        logger.error("Error processing command: %s", e)
                        error_result = CommandResult(success=False, message=str(e))
                        await ws.send(error_result.to_json())
        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            logger.warning("Connection lost: %s. Reconnecting in 5 seconds...", e)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error("Unexpected error: %s. Reconnecting in 5 seconds...", e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    config_file = os.environ.get("CONFIG_PATH", "agent/config.yaml")
    asyncio.run(run_agent(config_file))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_main.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agent/main.py tests/agent/test_main.py
git commit -m "feat(agent): add WebSocket client with command dispatcher and auto-reconnect"
```

---

### Task 13: Run all tests and final commit

**Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 2: Fix any failures**

If any test fails, fix it and re-run.

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: ensure all tests pass, project complete"
```

---

## Deployment Notes (not automated, for reference)

### VPS Setup

```bash
# On VPS
cd /opt/home_alice
pip install -r server/requirements.txt
cp server/config.example.yaml server/config.yaml
# Edit config.yaml with real tokens
uvicorn server.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile key.pem --ssl-certfile cert.pem
```

### Windows Agent Setup

```bash
# On Windows PC
pip install -r agent/requirements.txt
cp agent/config.example.yaml agent/config.yaml
# Edit config.yaml with server URL and API key
python agent/main.py
```

### Yandex Dialogs Setup

1. Go to https://dialogs.yandex.ru/developer/
2. Create new dialog → "Навык в Алисе"
3. Set webhook URL: `https://your-vps:8443/alice/webhook`
4. Test in the testing tab

### Getting API Tokens

**VK Token:** Create app at https://dev.vk.com/ → get user token with `video` scope
**YandexGPT:** Create service account in Yandex Cloud console → get API key
**Yandex Cloud Folder ID:** Visible in the Yandex Cloud console URL
