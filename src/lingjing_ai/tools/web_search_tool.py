import os

from lingjing_ai.agent.models import ToolResult
from lingjing_ai.config.settings import AppSettings


class WebSearchTool:
    name = "web_search"

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def run(self, query: str) -> ToolResult:
        if not self.settings.agent_use_web_search:
            return ToolResult(status="disabled", message="外部搜索未启用", data={"query": query})
        if not self.settings.web_search_api_url or not os.getenv(self.settings.web_search_api_key_env):
            return ToolResult(status="disabled", message="外部搜索未配置", data={"query": query})
        return ToolResult(status="disabled", message="外部搜索接口待接入", data={"query": query})
