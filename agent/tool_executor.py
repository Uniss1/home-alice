# agent/tool_executor.py
import logging
from agent.tools.system import shutdown, reboot, sleep_pc, get_system_info
from agent.tools.windows import list_windows, switch_window, close_window
from agent.tools.browser import open_url, search_vk_video
from agent.tools.audio import volume_set, volume_mute
from agent.tools.keyboard import press_keys, type_text
from agent.tools.process import list_processes, kill_process
from agent.tools.browser_control import BrowserController

logger = logging.getLogger(__name__)


class ToolExecutor:
    def __init__(self, vk_token: str = "", browser_cdp_url: str = "http://localhost:9222", allowed_commands: list[str] | None = None):
        self.vk_token = vk_token
        self.browser = BrowserController(browser_cdp_url)
        self.allowed_commands = allowed_commands or []

    def execute(self, tool_name: str, args: dict) -> str:
        try:
            match tool_name:
                case "shutdown":
                    return shutdown()
                case "reboot":
                    return reboot()
                case "sleep_pc":
                    return sleep_pc()
                case "get_system_info":
                    return get_system_info()
                case "list_windows":
                    return list_windows()
                case "switch_window":
                    return switch_window(args.get("title", ""))
                case "close_window":
                    return close_window(args.get("title", ""))
                case "open_url":
                    return open_url(args.get("url", ""))
                case "search_vk_video":
                    # NOTE: search_vk_video is synchronous (uses httpx.Client, not AsyncClient)
                    return search_vk_video(
                        args.get("query", ""),
                        self.vk_token,
                        args.get("channel_id"),
                    )
                case "volume_set":
                    return volume_set(args.get("level", 50))
                case "volume_mute":
                    return volume_mute(args.get("mute", True))
                case "press_keys":
                    return press_keys(args.get("keys", []))
                case "type_text":
                    return type_text(args.get("text", ""))
                case "list_processes":
                    return list_processes(args.get("top_n", 15))
                case "kill_process":
                    return kill_process(args.get("pid", 0))
                case "browser_list_tabs":
                    return self.browser.list_tabs()
                case "browser_pause_video":
                    return self.browser.pause_video()
                case "browser_play_video":
                    return self.browser.play_video()
                case "browser_search":
                    return self.browser.search(args.get("query", ""))
                case "run_command":
                    cmd = args.get("command", "")
                    if cmd.split()[0] not in self.allowed_commands:
                        return f"Команда «{cmd}» не в белом списке"
                    import subprocess
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=10
                    )
                    return result.stdout or result.stderr or "Выполнено"
                case _:
                    return f"Неизвестный инструмент: {tool_name}"
        except Exception as e:
            logger.error("Tool execution error: %s", e)
            return f"Ошибка: {e}"
