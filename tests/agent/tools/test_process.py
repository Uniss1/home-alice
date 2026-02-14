# tests/agent/tools/test_process.py
from unittest.mock import patch, MagicMock
from agent.tools.process import list_processes, kill_process


@patch("agent.tools.process.psutil.process_iter")
def test_list_processes(mock_iter):
    proc1 = MagicMock()
    proc1.info = {"pid": 1, "name": "chrome.exe", "cpu_percent": 5.0}
    proc2 = MagicMock()
    proc2.info = {"pid": 2, "name": "code.exe", "cpu_percent": 3.0}
    mock_iter.return_value = [proc1, proc2]

    result = list_processes()
    assert "chrome" in result.lower()


@patch("agent.tools.process.psutil.Process")
def test_kill_process(mock_proc_cls):
    mock_proc = MagicMock()
    mock_proc.name.return_value = "notepad.exe"
    mock_proc_cls.return_value = mock_proc

    result = kill_process(1234)
    mock_proc.kill.assert_called_once()
