# agent/llm_client.py
import json
import logging
from openai import OpenAI
from agent.config import LLMConfig
from agent.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — AI-агент для управления домашним компьютером через голосовые команды.
Пользователь говорит команду голосом через Алису, ты получаешь текст и выполняешь действия.

Правила:
- Выполняй команду, используя доступные инструменты
- Можешь вызывать несколько инструментов подряд если нужно
- Отвечай кратко — твой ответ будет озвучен Алисой (макс 1-2 предложения)
- Отвечай на русском языке"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "shutdown",
            "description": "Выключить компьютер",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reboot",
            "description": "Перезагрузить компьютер",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sleep_pc",
            "description": "Перевести компьютер в спящий режим",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Получить информацию о системе (CPU, RAM, диск)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_windows",
            "description": "Показать список открытых окон",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_window",
            "description": "Переключиться на окно по части заголовка",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Часть заголовка окна (например 'Chrome', 'VS Code')"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_window",
            "description": "Закрыть окно по части заголовка",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Часть заголовка окна"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Открыть URL в браузере",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL для открытия"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_vk_video",
            "description": "Найти и открыть видео на VK Video по запросу (самое популярное)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                    "channel_id": {"type": "integer", "description": "ID канала VK (опционально)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_set",
            "description": "Установить громкость от 0 до 100",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Уровень громкости (0-100)"},
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_mute",
            "description": "Включить или выключить звук (mute)",
            "parameters": {
                "type": "object",
                "properties": {
                    "mute": {"type": "boolean", "description": "true — выключить звук, false — включить"},
                },
                "required": ["mute"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_keys",
            "description": "Нажать комбинацию клавиш (горячие клавиши)",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список клавиш (например ['ctrl', 'c'], ['alt', 'tab'])",
                    },
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Напечатать текст на клавиатуре",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Текст для ввода"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "Показать список запущенных процессов (топ по CPU)",
            "parameters": {
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer", "description": "Сколько процессов показать (по умолчанию 15)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_process",
            "description": "Завершить процесс по PID",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "ID процесса"},
                },
                "required": ["pid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Выполнить системную команду (только из белого списка)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Команда для выполнения"},
                },
                "required": ["command"],
            },
        },
    },
]


class LLMClient:
    def __init__(self, config: LLMConfig, vk_token: str = "", allowed_commands: list[str] | None = None):
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)
        self.model = config.model
        self.executor = ToolExecutor(vk_token=vk_token, allowed_commands=allowed_commands)

    def get_tool_definitions(self) -> list[dict]:
        return TOOL_DEFINITIONS

    def process_command(self, user_text: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        try:
            # Up to 3 rounds of tool calls
            for _ in range(3):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                )

                choice = response.choices[0]

                # If no tool calls — return the text response
                if not choice.message.tool_calls:
                    return choice.message.content or "Готово"

                # Execute tool calls
                messages.append(choice.message)
                for tool_call in choice.message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)
                    logger.info("Calling tool: %s(%s)", fn_name, fn_args)
                    result = self.executor.execute(fn_name, fn_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

            # If we exhausted rounds, get final response
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return response.choices[0].message.content or "Готово"

        except Exception as e:
            logger.error("LLM error: %s", e)
            return f"Не удалось обработать команду: {e}"
