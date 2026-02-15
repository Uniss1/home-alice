# tests/agent/tools/test_audio.py
from unittest.mock import patch, MagicMock
from agent.tools.audio import volume_set, volume_mute


@patch("shared.volume._get_volume_interface")
def test_volume_set(mock_iface):
    mock_vol = MagicMock()
    mock_iface.return_value = mock_vol
    result = volume_set(75)
    mock_vol.SetMasterVolumeLevelScalar.assert_called_once_with(0.75, None)
    assert "75" in result


@patch("shared.volume._get_volume_interface")
def test_volume_set_clamps_above_100(mock_iface):
    mock_vol = MagicMock()
    mock_iface.return_value = mock_vol
    volume_set(150)
    mock_vol.SetMasterVolumeLevelScalar.assert_called_once_with(1.0, None)


@patch("shared.volume._get_volume_interface")
def test_volume_set_clamps_below_0(mock_iface):
    mock_vol = MagicMock()
    mock_iface.return_value = mock_vol
    volume_set(-10)
    mock_vol.SetMasterVolumeLevelScalar.assert_called_once_with(0.0, None)


@patch("shared.volume._get_volume_interface")
def test_volume_mute_true(mock_iface):
    mock_vol = MagicMock()
    mock_iface.return_value = mock_vol
    result = volume_mute(True)
    mock_vol.SetMute.assert_called_once_with(1, None)
    assert "выключен" in result.lower()


@patch("shared.volume._get_volume_interface")
def test_volume_mute_false(mock_iface):
    mock_vol = MagicMock()
    mock_iface.return_value = mock_vol
    result = volume_mute(False)
    mock_vol.SetMute.assert_called_once_with(0, None)
    assert "включён" in result.lower()


@patch("shared.volume._get_volume_interface")
def test_volume_set_handles_exception(mock_iface):
    mock_iface.side_effect = Exception("Test error")
    result = volume_set(50)
    assert "Ошибка" in result


@patch("shared.volume._get_volume_interface")
def test_volume_mute_handles_exception(mock_iface):
    mock_iface.side_effect = Exception("Test error")
    result = volume_mute(True)
    assert "Ошибка" in result
