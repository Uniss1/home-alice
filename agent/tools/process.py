# agent/tools/process.py
import logging
import psutil

logger = logging.getLogger(__name__)


def list_processes(top_n: int = 15) -> str:
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
            procs.append(p.info)
        procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
        lines = [
            f"  {p['name']} (PID {p['pid']}, CPU {p.get('cpu_percent', 0):.1f}%)"
            for p in procs[:top_n]
        ]
        return "Топ процессов:\n" + "\n".join(lines)
    except Exception as e:
        return f"Ошибка: {e}"


def kill_process(pid: int) -> str:
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill()
        return f"Завершил процесс {name} (PID {pid})"
    except psutil.NoSuchProcess:
        return f"Процесс с PID {pid} не найден"
    except Exception as e:
        return f"Ошибка: {e}"
