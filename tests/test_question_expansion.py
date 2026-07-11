from lingjing_ai.services.conversation import ConversationMessage
from lingjing_ai.services.question_expansion import (
    QwenQuestionExpander,
    expand_question,
    rank_question_candidates,
)


class FakeExpansionClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages = []

    def chat(self, messages):
        self.messages = messages
        return self.content


class FailingExpansionClient:
    def chat(self, messages):
        raise RuntimeError("model unavailable")


def test_expand_question_uses_qwen_client_json_candidates():
    client = FakeExpansionClient(
        '["灵山胜境游览路线怎么安排", "灵山胜境五小时核心景点路线", "灵山胜境轻松游玩顺序"]'
    )

    candidates = expand_question(
        "我览灵山胜境，请帮我规划路线想用五小时游玩时",
        target="灵山胜境",
        history=[],
        max_candidates=8,
        expander=QwenQuestionExpander(client, model_name="qwen3.7-plus"),
    )

    assert candidates == [
        "我览灵山胜境，请帮我规划路线想用五小时游玩时",
        "灵山胜境游览路线怎么安排",
        "灵山胜境五小时核心景点路线",
        "灵山胜境轻松游玩顺序",
    ]
    assert "qwen3.7-plus" in client.messages[0]["content"]


def test_expand_question_without_model_does_not_use_local_rule_expansion():
    candidates = expand_question(
        "怎么玩",
        target="灵山胜境",
        history=[ConversationMessage(role="user", content="我想去灵山胜境游玩")],
        max_candidates=8,
        expander=None,
    )

    assert candidates == ["怎么玩"]


def test_expand_question_model_failure_returns_original_only():
    candidates = expand_question(
        "我览灵山胜境，请帮我规划路线想用五小时游玩时",
        "灵山胜境",
        [],
        8,
        expander=QwenQuestionExpander(FailingExpansionClient(), model_name="qwen3.7-plus"),
    )

    assert candidates == ["我览灵山胜境，请帮我规划路线想用五小时游玩时"]


def test_rank_question_candidates_prefers_candidates_that_match_records():
    candidates = [
        "灵山胜境有什么特色",
        "灵山胜境五小时游览路线怎么安排",
        "灵山胜境门票优惠政策",
        "灵山胜境餐饮住宿推荐",
    ]
    records = [
        {
            "document_name": "灵山胜境路线资料.md",
            "content": "五小时游览路线建议经过灵山大佛、九龙灌浴、灵山梵宫，并结合观光车和休息区安排。",
            "metadata": {"category": "游览路线"},
        }
    ]

    ranked = rank_question_candidates("五小时游灵山胜境", candidates, records, top_n=3)

    assert ranked[0] == "灵山胜境五小时游览路线怎么安排"
    assert len(ranked) == 3
