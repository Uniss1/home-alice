# agent/llm_client.py
import json
import logging
import httpx
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
            "name": "browser_list_tabs",
            "description": "Показать список открытых вкладок браузера (с пометкой где играет видео)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_pause_video",
            "description": "Поставить видео на паузу в браузере (найдёт вкладку с играющим видео автоматически)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_play_video",
            "description": "Продолжить воспроизведение видео в браузере (снять с паузы)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_search",
            "description": "Найти поле поиска на текущей странице в браузере и ввести запрос",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                },
                "required": ["query"],
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


def _yandex_tools() -> list[dict]:
    """Convert tool definitions to YandexGPT format."""
    return [{"function": t["function"]} for t in TOOL_DEFINITIONS]


class LLMClient:
    def __init__(self, config: LLMConfig, vk_token: str = "", browser_cdp_url: str = "http://localhost:9222", allowed_commands: list[str] | None = None):
        self.provider = config.provider
        self.model = config.model
        self.executor = ToolExecutor(vk_token=vk_token, browser_cdp_url=browser_cdp_url, allowed_commands=allowed_commands)

        if self.provider == "yandexgpt":
            self.folder_id = config.folder_id
            self.yandex_api_key = config.api_key
            self.yandex_base_url = config.base_url
        else:
            self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def get_tool_definitions(self) -> list[dict]:
        return TOOL_DEFINITIONS

    def process_command(self, user_text: str) -> str:
        if self.provider == "yandexgpt":
            return self._process_yandexgpt(user_text)
        return self._process_openai(user_text)

    def _process_openai(self, user_text: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        try:
            for _ in range(3):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                )

                choice = response.choices[0]

                if not choice.message.tool_calls:
                    return choice.message.content or "Готово"

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

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return response.choices[0].message.content or "Готово"

        except Exception as e:
            logger.error("LLM error: %s", e)
            return f"Не удалось обработать команду: {e}"

    def _process_yandexgpt(self, user_text: str) -> str:
        model_uri = f"gpt://{self.folder_id}/{self.model}"
        messages = [
            {"role": "system", "text": SYSTEM_PROMPT},
            {"role": "user", "text": user_text},
        ]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {self.yandex_api_key}",
            "x-folder-id": self.folder_id,
            "x-data-logging-enabled": "false",
        }

        url = f"{self.yandex_base_url}/foundationModels/v1/completion"

        try:
            for _ in range(3):
                body = {
                    "modelUri": model_uri,
                    "completionOptions": {
                        "stream": False,
                        "temperature": 0.3,
                        "maxTokens": 1000,
                    },
                    "messages": messages,
                    "tools": _yandex_tools(),
                }

                resp = httpx.post(url, headers=headers, json=body, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                alt = data["result"]["alternatives"][0]
                msg = alt["message"]

                # No tool calls — return text
                if "toolCallList" not in msg:
                    return msg.get("text", "Готово")

                # Execute tool calls
                tool_calls = msg["toolCallList"]["toolCalls"]
                messages.append(msg)

                for tc in tool_calls:
                    fc = tc["functionCall"]
                    fn_name = fc["name"]
                    fn_args = fc.get("arguments", {})
                    logger.info("Calling tool: %s(%s)", fn_name, fn_args)
                    result = self.executor.execute(fn_name, fn_args)

                    messages.append({
                        "role": "assistant",
                        "toolResultList": {
                            "toolResults": [{
                                "functionResult": {
                                    "name": fn_name,
                                    "content": result,
                                }
                            }]
                        },
                    })

            # Final response without tools
            body = {
                "modelUri": model_uri,
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.3,
                    "maxTokens": 1000,
                },
                "messages": messages,
            }
            resp = httpx.post(url, headers=headers, json=body, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data["result"]["alternatives"][0]["message"].get("text", "Готово")

        except Exception as e:
            logger.error("LLM error: %s", e)
            return f"Не удалось обработать команду: {e}"
