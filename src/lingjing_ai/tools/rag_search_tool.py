from lingjing_ai.agent.models import ToolResult
from lingjing_ai.rag.pipeline import RagPipeline


class RagSearchTool:
    name = "rag_search"

    def __init__(self, pipeline: RagPipeline) -> None:
        self.pipeline = pipeline

    def run(self, query: str) -> ToolResult:
        sources = self.pipeline.search_sources(query)
        status = "ok" if sources else "empty"
        message = "已检索本地知识库" if sources else "本地知识库未命中可靠资料"
        return ToolResult(status=status, message=message, sources=sources)
