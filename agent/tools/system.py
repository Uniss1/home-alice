# agent/tools/system.py
import subprocess
import logging
import psutil

logger = logging.getLogger(__name__)


def shutdown() -> str:
    try:
        subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
        return "Выключаю компьютер"
    except Exception as e:
        return f"Ошибка при выключении: {e}"


def reboot() -> str:
    try:
        subprocess.run(["shutdown", "/r", "/t", "0"], check=True)
        return "Перезагружаю компьютер"
    except Exception as e:
        return f"Ошибка при перезагрузке: {e}"


def sleep_pc() -> str:
    try:
        subprocess.run(
            ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True
        )
        return "Перевожу в спящий режим"
    except Exception as e:
        return f"Ошибка: {e}"


def get_system_info() -> str:
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return (
            f"CPU: {cpu}%, "
            f"RAM: {mem.percent}% ({mem.total // (1024**3)} GB), "
            f"Диск: {disk.percent}% ({disk.total // (1024**3)} GB)"
        )
    except Exception as e:
        return f"Ошибка: {e}"
