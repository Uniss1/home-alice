"""LLM fallback intent router via Ollama."""

import httpx

from media_assistant.intents.types import Intent, IntentType

SYSTEM_PROMPT = """Ты — голосовой ассистент для управления медиа и компьютером.
Пользователь даёт голосовую команду. Определи намерение и вызови нужный инструмент.
Если команда не подходит ни под один инструмент, не вызывай инструменты."""

# Map tool function names to IntentType
_TOOL_NAME_TO_INTENT = {member.value: member for member in IntentType if member != IntentType.UNKNOWN}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "play_media",
            "description": "Включить медиа (музыку, видео, фильм)",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Что включить"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pause",
            "description": "Поставить на паузу",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume",
            "description": "Продолжить воспроизведение",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_set",
            "description": "Установить громкость",
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "integer"}},
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_up",
            "description": "Увеличить громкость",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_down",
            "description": "Уменьшить громкость",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shutdown",
            "description": "Выключить компьютер",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reboot",
            "description": "Перезагрузить компьютер",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fullscreen",
            "description": "Включить полноэкранный режим",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close",
            "description": "Закрыть текущее окно",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "next_track",
            "description": "Следующий трек",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prev_track",
            "description": "Предыдущий трек",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class LLMFallbackRouter:
    """Classify commands via local LLM when regex patterns don't match."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen3:4b",
    ):
        self.ollama_url = ollama_url
        self.model = model

    def route(self, text: str) -> Intent:
        """Send unrecognized text to LLM, parse tool call as intent."""
        try:
            resp = httpx.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "tools": TOOLS,
                    "stream": False,
                },
                timeout=5.0,
            )
        except (httpx.TimeoutException, httpx.ConnectError):
            return Intent(type=IntentType.UNKNOWN, query=text)

        data = resp.json()
        tool_calls = data.get("message", {}).get("tool_calls", [])
        if not tool_calls:
            return Intent(type=IntentType.UNKNOWN, query=text)

        call = tool_calls[0]
        func_name = call["function"]["name"]
        args = call["function"].get("arguments", {})

        intent_type = _TOOL_NAME_TO_INTENT.get(func_name, IntentType.UNKNOWN)
        if intent_type == IntentType.UNKNOWN:
            return Intent(type=IntentType.UNKNOWN, query=text)

        return Intent(
            type=intent_type,
            query=args.get("query", ""),
            params={k: v for k, v in args.items() if k != "query"},
        )

    def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = httpx.get(f"{self.ollama_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except httpx.ConnectError:
            return False
