from dataclasses import replace
from pathlib import Path

import pytest

from lingjing_ai.agent.models import AgentEvidence, ToolTrace
from lingjing_ai.config.settings import AppSettings
from lingjing_ai.models.rag import SourceChunk
from lingjing_ai.realtime.conversation import RealtimeConversationService
from lingjing_ai.services.conversation_store import ConversationStore


class FakeAgentExecutor:
    def __init__(self) -> None:
        self.contexts = []

    def collect_evidence(self, question, conversation_context=None):
        self.contexts.append(conversation_context)
        return AgentEvidence(
            question=conversation_context.standalone_question,
            sources=[
                SourceChunk(
                    chunk_id="chunk_1",
                    document_id="doc_1",
                    document_name="灵山资料.md",
                    content="灵山胜境开放时间以景区当日公告为准。",
                    score=0.88,
                    metadata={"section_path": "游览信息"},
                )
            ],
            confidence=0.88,
            is_answered=True,
            trace_id="trace_1",
            tool_trace=[ToolTrace("rag_search", question, "ok", "命中资料", 1)],
        )


def build_service(tmp_path: Path):
    settings = replace(
        AppSettings.for_workspace(tmp_path),
        question_expansion_enabled=False,
    )
    store = ConversationStore(tmp_path / "conversations.db")
    agent = FakeAgentExecutor()
    return RealtimeConversationService(settings, store, agent), store, agent


def test_prepare_turn_creates_session_and_formats_temporary_evidence(tmp_path: Path):
    service, store, _ = build_service(tmp_path)

    prepared = service.prepare_turn("灵山胜境几点开放？", "visitor_a", "")

    assert prepared.session.session_id.startswith("sess_")
    assert prepared.evidence.question == "灵山胜境几点开放？"
    assert "临时证据" in prepared.evidence_prompt
    assert "灵山资料.md" in prepared.evidence_prompt
    assert store.list_messages(prepared.session.session_id, "visitor_a") == []


def test_prepare_turn_writes_mode_specific_answer_contract_into_evidence_prompt(tmp_path: Path):
    service, _, _ = build_service(tmp_path)

    regular = service.prepare_turn("灵山胜境有什么特色？", "visitor_a", "", mode="text")
    avatar = service.prepare_turn(
        "灵山胜境有什么特色？",
        "visitor_a",
        regular.session.session_id,
        mode="avatar",
    )

    assert regular.answer_contract.profile == "text_detailed"
    assert "300—600字" in regular.evidence_prompt
    assert avatar.answer_contract.profile == "avatar_summary"
    assert "3—6句" in avatar.evidence_prompt


def test_prepare_turn_uses_same_session_history_across_modes(tmp_path: Path):
    service, store, agent = build_service(tmp_path)
    first = service.prepare_turn("灵山胜境有什么特色？", "visitor_a", "")
    service.persist_completed(first, "灵山胜境以灵山大佛闻名。")

    second = service.prepare_turn("那开放时间呢？", "visitor_a", first.session.session_id)

    assert second.session.session_id == first.session.session_id
    assert "灵山胜境" in second.evidence.question
    assert agent.contexts[-1].history[-1].role == "assistant"
    assert [message["role"] for message in service.upstream_history(first.session.session_id, "visitor_a")] == [
        "user",
        "assistant",
    ]


def test_prepare_turn_preserves_explicit_internal_route_in_existing_session(tmp_path: Path):
    service, _, agent = build_service(tmp_path)
    first = service.prepare_turn("灵山胜境适合老人的游玩路线", "visitor_a", "")
    service.persist_completed(first, "建议先游览灵山大佛。")

    route = service.prepare_turn(
        "从五明桥到五智门怎么走",
        "visitor_a",
        first.session.session_id,
    )

    assert route.evidence.question == "从五明桥到五智门怎么走"
    assert route.evidence.needs_clarification is False
    assert agent.contexts[-1].standalone_question == "从五明桥到五智门怎么走"


def test_completed_turn_is_persisted_once_and_wrong_visitor_is_rejected(tmp_path: Path):
    service, store, _ = build_service(tmp_path)
    prepared = service.prepare_turn("灵山胜境几点开放？", "visitor_a", "")

    service.persist_completed(prepared, "开放时间以景区公告为准。", "turn_1")
    service.persist_completed(prepared, "这条重复回答不应写入。", "turn_1")

    messages = store.list_messages(prepared.session.session_id, "visitor_a")
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[-1].sources[0]["document_name"] == "灵山资料.md"
    with pytest.raises(PermissionError):
        service.prepare_turn("继续问", "visitor_b", prepared.session.session_id)
