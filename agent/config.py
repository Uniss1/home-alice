# agent/config.py
from dataclasses import dataclass, field
import yaml


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    folder_id: str = ""


@dataclass
class AgentConfig:
    server_url: str
    api_key: str
    llm: LLMConfig
    vk_token: str = ""
    browser_cdp_url: str = "http://localhost:9222"
    allowed_commands: list[str] = field(default_factory=list)


def load_config(path: str) -> AgentConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    llm_data = data["llm"]
    return AgentConfig(
        server_url=data["server_url"],
        api_key=data["api_key"],
        llm=LLMConfig(
            provider=llm_data["provider"],
            api_key=llm_data["api_key"],
            base_url=llm_data["base_url"],
            model=llm_data["model"],
            folder_id=llm_data.get("folder_id", ""),
        ),
        vk_token=data.get("vk_token", ""),
        browser_cdp_url=data.get("browser_cdp_url", "http://localhost:9222"),
        allowed_commands=data.get("allowed_commands", []),
    )
