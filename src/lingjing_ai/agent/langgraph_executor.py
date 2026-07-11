from __future__ import annotations

from collections.abc import Iterator
import uuid
from typing import Any, TypedDict

from lingjing_ai.agent.executor import AgentExecutor, _preferred_tool_source_type
from lingjing_ai.agent.models import AgentAnswer, AgentPlan, AgentStep, ToolTrace
from lingjing_ai.config.settings import AppSettings
from lingjing_ai.models.rag import SourceChunk
from lingjing_ai.services.conversation import ConversationContext

try:
    from langgraph.graph import END, StateGraph
except ImportError:
    END = "__end__"
    StateGraph = None


class AgentGraphState(TypedDict, total=False):
    original_question: str
    active_question: str
    conversation_context: ConversationContext | None
    plan: AgentPlan
    queries: list[str]
    tool_trace: list[ToolTrace]
    raw_sources: list[SourceChunk]
    sources: list[SourceChunk]
    loops: int
    used_questions: list[str]
    final_answer: str
    result: AgentAnswer
    next_step: str


class LangGraphAgentExecutor(AgentExecutor):
    def __init__(self, settings: AppSettings, tools: list[Any]) -> None:
        if StateGraph is None:
            raise RuntimeError("LangGraph 未安装，请先安装 langgraph，或将 AGENT_EXECUTOR_MODE 设置为 legacy。")
        super().__init__(settings=settings, tools=tools)
        self.graph = self._build_graph()

    def run(self, question: str, conversation_context: ConversationContext | None = None) -> AgentAnswer:
        active_question = self._active_question(question, conversation_context)
        if conversation_context and conversation_context.needs_clarification:
            result = AgentAnswer(
                answer=conversation_context.clarifying_question,
                sources=[],
                confidence=0.0,
                is_answered=False,
                trace_id=f"agent_{uuid.uuid4().hex}",
                tool_trace=[],
                needs_clarification=True,
                clarifying_question=conversation_context.clarifying_question,
            )
            self._write_agent_log(active_question, result)
            return result
        fast_result = self._run_fast_tool_answer(active_question, conversation_context)
        if fast_result is not None:
            self._write_agent_log(active_question, fast_result)
            return fast_result

        state: AgentGraphState = {
            "original_question": question,
            "active_question": active_question,
            "conversation_context": conversation_context,
            "queries": [active_question],
            "tool_trace": [],
            "raw_sources": [],
            "sources": [],
            "loops": 0,
            "used_questions": [active_question],
        }
        final_state = self.graph.invoke(state)
        result = final_state["result"]
        self._write_agent_log(final_state["active_question"], result)
        return result

    def run_stream(self, question: str, conversation_context: ConversationContext | None = None) -> Iterator[dict[str, Any]]:
        yield from super().run_stream(question, conversation_context=conversation_context)

    def _build_graph(self):
        graph = StateGraph(AgentGraphState)
        graph.add_node("prepare_context", self._prepare_context)
        graph.add_node("plan_tools", self._plan_tools)
        graph.add_node("route_tools", self._route_tools)
        graph.add_node("run_tools", self._run_tools_node)
        graph.add_node("merge_sources", self._merge_sources)
        graph.add_node("reflect", self._reflect)
        graph.add_node("generate_answer", self._answer)
        graph.set_entry_point("prepare_context")
        graph.add_edge("prepare_context", "plan_tools")
        graph.add_edge("plan_tools", "route_tools")
        graph.add_edge("route_tools", "run_tools")
        graph.add_edge("run_tools", "merge_sources")
        graph.add_edge("merge_sources", "reflect")
        graph.add_conditional_edges(
            "reflect",
            self._next_after_reflection,
            {"retry": "plan_tools", "answer": "generate_answer"},
        )
        graph.add_edge("generate_answer", END)
        return graph.compile()

    def _prepare_context(self, state: AgentGraphState) -> AgentGraphState:
        return state

    def _plan_tools(self, state: AgentGraphState) -> AgentGraphState:
        plan = self.planner.plan(state["active_question"])
        return {**state, "plan": plan, "queries": [state["active_question"]]}

    def _route_tools(self, state: AgentGraphState) -> AgentGraphState:
        steps = list(state["plan"].steps)
        routed_steps = self._prioritized_steps(state["active_question"], steps)
        return {**state, "plan": AgentPlan(question=state["active_question"], steps=routed_steps)}

    def _run_tools_node(self, state: AgentGraphState) -> AgentGraphState:
        queries = list(state.get("queries", [state["active_question"]]))
        traces = list(state.get("tool_trace", []))
        sources = list(state.get("raw_sources", []))
        for step in state["plan"].steps:
            tool = self.tools.get(step.tool_name)
            if tool is None:
                traces.append(ToolTrace(step.tool_name, step.tool_input, "skipped", "工具未注册"))
                continue
            result = self._run_tool(tool, step.tool_input, queries)
            traces.append(
                ToolTrace(
                    tool_name=step.tool_name,
                    tool_input=step.tool_input,
                    status=result.status,
                    message=result.message,
                    source_count=len(result.sources),
                )
            )
            if step.tool_name == "query_rewrite" and result.data.get("queries"):
                queries = result.data["queries"][:3]
            sources.extend(result.sources)
        return {**state, "queries": queries, "tool_trace": traces, "raw_sources": sources}

    def _merge_sources(self, state: AgentGraphState) -> AgentGraphState:
        ranked_sources = self._compress_sources(
            self._prioritize_sources(
                state["active_question"],
                self._dedupe_sources(state.get("raw_sources", [])),
            )
        )
        return {**state, "sources": ranked_sources}

    def _reflect(self, state: AgentGraphState) -> AgentGraphState:
        if not self.settings.langgraph_reflection_enabled or state.get("sources"):
            return {**state, "next_step": "answer"}
        if state.get("loops", 0) >= self.settings.langgraph_max_loops:
            return {**state, "next_step": "answer"}
        retry_question = self._next_retry_question(state)
        return {
            **state,
            "active_question": retry_question,
            "loops": state.get("loops", 0) + 1,
            "used_questions": [*state.get("used_questions", []), retry_question],
            "raw_sources": [],
            "sources": [],
            "next_step": "retry",
        }

    def _answer(self, state: AgentGraphState) -> AgentGraphState:
        context = state.get("conversation_context")
        answer = self._apply_assumptions(
            self._generate_answer(state["active_question"], state.get("sources", []), context),
            context,
        )
        sources = state.get("sources", [])
        result = AgentAnswer(
            answer=answer,
            sources=sources,
            confidence=sources[0].score if sources else 0.0,
            is_answered=bool(sources),
            trace_id=f"agent_{uuid.uuid4().hex}",
            tool_trace=state.get("tool_trace", []),
        )
        return {**state, "final_answer": answer, "result": result}

    def _next_after_reflection(self, state: AgentGraphState) -> str:
        return state.get("next_step", "answer")

    def _prioritized_steps(self, question: str, steps: list[AgentStep]) -> list[AgentStep]:
        preferred_tool = self._preferred_tool_name(question)
        if preferred_tool is None:
            return steps[: self.settings.agent_max_steps]
        by_name = {step.tool_name: step for step in steps}
        ordered_names = ["query_rewrite", preferred_tool, "kg_search", "rag_search", "document_search", "web_search"]
        routed = [by_name[name] for name in ordered_names if name in by_name]
        routed.extend(step for step in steps if step.tool_name not in {item.tool_name for item in routed})
        return routed[: self.settings.agent_max_steps]

    def _preferred_tool_name(self, question: str) -> str | None:
        source_type = _preferred_tool_source_type(question)
        return {
            "amap_weather": "amap_weather",
            "amap_route": "amap_route",
            "amap_place": "amap_place_search",
        }.get(source_type)

    def _next_retry_question(self, state: AgentGraphState) -> str:
        context = state.get("conversation_context")
        candidates = []
        if context:
            candidates.extend(context.selected_questions or [])
            candidates.extend(context.expanded_questions or [])
            candidates.append(context.standalone_question)
        candidates.extend(state.get("queries", []))
        candidates.append(f"{state['active_question']} 详细资料")
        used = set(state.get("used_questions", []))
        for candidate in candidates:
            normalized = candidate.strip()
            if normalized and normalized not in used:
                return normalized
        return f"{state['active_question']} 详细资料"
