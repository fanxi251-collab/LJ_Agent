from dataclasses import dataclass, field

from lingjing_ai.models.rag import SourceChunk


@dataclass(frozen=True)
class AgentStep:
    tool_name: str
    tool_input: str


@dataclass(frozen=True)
class AgentPlan:
    question: str
    steps: list[AgentStep]


@dataclass(frozen=True)
class ToolTrace:
    tool_name: str
    tool_input: str
    status: str
    message: str
    source_count: int = 0


@dataclass(frozen=True)
class ToolResult:
    status: str
    message: str
    data: dict = field(default_factory=dict)
    sources: list[SourceChunk] = field(default_factory=list)


@dataclass(frozen=True)
class AgentAnswer:
    answer: str
    sources: list[SourceChunk]
    confidence: float
    is_answered: bool
    trace_id: str
    tool_trace: list[ToolTrace]
    needs_clarification: bool = False
    clarifying_question: str = ""


@dataclass(frozen=True)
class AgentEvidence:
    question: str
    sources: list[SourceChunk]
    confidence: float
    is_answered: bool
    trace_id: str
    tool_trace: list[ToolTrace]
    needs_clarification: bool = False
    clarifying_question: str = ""
