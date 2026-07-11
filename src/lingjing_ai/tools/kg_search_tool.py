from lingjing_ai.agent.models import ToolResult
from lingjing_ai.kg.extractor import classify_kg_scenario
from lingjing_ai.rag.pipeline import RagPipeline


class KnowledgeGraphSearchTool:
    name = "kg_search"

    def __init__(self, pipeline: RagPipeline) -> None:
        self.pipeline = pipeline

    def run(self, query: str) -> ToolResult:
        scenario = classify_kg_scenario(query)
        sources = self.pipeline.knowledge_graph.search(query, top_k=self.pipeline.settings.top_k, scenario=scenario)
        status = "ok" if sources else "empty"
        message = "已检索知识图谱" if sources else "知识图谱未命中相关关系"
        if not self.pipeline.knowledge_graph.status().get("enabled"):
            status = "disabled"
            message = self.pipeline.knowledge_graph.status().get("message", "知识图谱未启用")
        return ToolResult(status=status, message=message, sources=sources)
