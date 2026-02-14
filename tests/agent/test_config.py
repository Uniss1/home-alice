# tests/agent/test_config.py
import os
import tempfile
import yaml
from agent.config import load_config, AgentConfig


def test_load_config():
    data = {
        "server_url": "wss://example.com/ws",
        "api_key": "test-key",
        "llm": {
            "provider": "glm4",
            "api_key": "glm-key",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4",
        },
        "vk_token": "vk-token",
        "allowed_commands": ["ipconfig", "tasklist"],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        path = f.name
    try:
        config = load_config(path)
        assert isinstance(config, AgentConfig)
        assert config.server_url == "wss://example.com/ws"
        assert config.llm.model == "glm-4"
        assert config.allowed_commands == ["ipconfig", "tasklist"]
    finally:
        os.unlink(path)
