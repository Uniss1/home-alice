# tests/agent/test_llm_client.py
from unittest.mock import patch, MagicMock
import pytest
from agent.llm_client import LLMClient
from agent.config import LLMConfig


@pytest.fixture
def llm_config():
    return LLMConfig(
        provider="glm4",
        api_key="test-key",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4",
    )


def test_get_tool_definitions(llm_config):
    client = LLMClient(llm_config, vk_token="", allowed_commands=[])
    tools = client.get_tool_definitions()
    assert isinstance(tools, list)
    assert len(tools) > 0
    # Each tool should have type, function with name, description, parameters
    for tool in tools:
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]


def test_tool_executor_shutdown(llm_config):
    from agent.tool_executor import ToolExecutor
    executor = ToolExecutor(vk_token="", allowed_commands=[])
    with patch("agent.tools.system.subprocess.run"):
        result = executor.execute("shutdown", {})
    assert isinstance(result, str)
