from lingjing_ai.agent.models import ToolResult
from lingjing_ai.rag.question_type import classify_question


class QueryRewriteTool:
    name = "query_rewrite"

    def run(self, question: str) -> ToolResult:
        queries = [question.strip()]
        expanded = self._expand(question)
        for query in expanded:
            if query and query not in queries:
                queries.append(query)
            if len(queries) >= 3:
                break
        return ToolResult(status="ok", message="已生成检索 query", data={"queries": queries})

    def _expand(self, question: str) -> list[str]:
        normalized = question.strip()
        profile = classify_question(normalized)
        expansions: list[str] = []
        if profile.category == "服务设施":
            expansions.append(f"{normalized} 老人 休息点 无障碍 游览建议")
        if profile.category == "票务价格":
            expansions.append(f"{normalized} 门票 票价 优惠政策")
        if profile.category == "开放时间":
            expansions.append(f"{normalized} 开放时间 演出安排 公告")
        if profile.category == "游览路线":
            expansions.append(f"{normalized} 游览路线 停车场 自驾 推荐顺序")
        if profile.category == "餐饮住宿":
            expansions.append(f"{normalized} 餐饮 住宿 餐厅 酒店 推荐")
        if profile.category == "活动表演":
            expansions.append(f"{normalized} 表演 活动 节目 场次 演出安排")
        if profile.category == "景点介绍":
            expansions.append(f"{normalized} 景点特色 核心景观 文化体验")
        return expansions or [normalized]
