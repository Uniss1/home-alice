# tests/agent/tools/test_system.py
from unittest.mock import patch, MagicMock
from agent.tools.system import shutdown, reboot, sleep_pc, get_system_info


@patch("shared.system.subprocess.run")
def test_shutdown(mock_run):
    result = shutdown()
    mock_run.assert_called_once_with(["shutdown", "/s", "/t", "0"], check=True)
    assert "выключаю" in result.lower() or "shutdown" in result.lower()


@patch("shared.system.subprocess.run")
def test_reboot(mock_run):
    result = reboot()
    mock_run.assert_called_once_with(["shutdown", "/r", "/t", "0"], check=True)
    assert "перезагружаю" in result.lower() or "reboot" in result.lower()


@patch("shared.system.subprocess.run")
def test_sleep_pc(mock_run):
    result = sleep_pc()
    assert mock_run.called


@patch("shared.system.psutil")
def test_get_system_info(mock_psutil):
    mock_psutil.cpu_percent.return_value = 25.0
    mock_psutil.virtual_memory.return_value = MagicMock(percent=60.0, total=16 * 1024**3)
    mock_psutil.disk_usage.return_value = MagicMock(percent=45.0, total=500 * 1024**3)
    result = get_system_info()
    assert "CPU" in result or "cpu" in result
