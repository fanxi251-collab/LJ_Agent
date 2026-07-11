from lingjing_ai.services.conversation import ConversationMessage, build_conversation_context
from lingjing_ai.services.question_expansion import QwenQuestionExpander


class FakeExpansionClient:
    def __init__(self):
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        return '["灵山胜境五小时游览路线怎么安排", "灵山胜境五小时轻松游览顺序", "灵山胜境五小时核心景点游览路线"]'


def test_follow_up_ticket_question_uses_recent_scenic_context():
    context = build_conversation_context(
        "那门票呢？",
        [
            ConversationMessage(role="user", content="灵山胜境有什么特色？"),
            ConversationMessage(role="assistant", content="灵山胜境以灵山大佛和梵宫文化体验闻名。"),
        ],
    )

    assert context.needs_clarification is False
    assert context.standalone_question == "灵山胜境门票信息"
    assert "灵山胜境" in context.context_summary


def test_route_follow_up_with_destination_context_asks_for_missing_origin():
    context = build_conversation_context(
        "怎么去？",
        [
            ConversationMessage(role="user", content="介绍一下灵山胜境"),
            ConversationMessage(role="assistant", content="灵山胜境位于无锡，是热门景区。"),
        ],
    )

    assert context.needs_clarification is True
    assert context.standalone_question == "到灵山胜境怎么去？"
    assert context.clarifying_question == "请告诉我您的出发地和目的地。"


def test_weather_question_without_place_asks_for_clarification():
    context = build_conversation_context("今日天气如何？", [])

    assert context.needs_clarification is True
    assert context.clarifying_question == "您想查询哪个城市或景区的天气？"


def test_weather_question_uses_recent_scenic_context():
    context = build_conversation_context(
        "今日天气如何？",
        [ConversationMessage(role="user", content="我想去灵山胜境游玩")],
    )

    assert context.needs_clarification is False
    assert context.standalone_question == "灵山胜境今日天气如何？"


def test_ticket_discount_question_without_identity_does_not_block_answer():
    context = build_conversation_context("灵山胜境门票有优惠吗？", [])

    assert context.needs_clarification is False
    assert context.clarifying_question == ""


def test_route_planning_question_without_people_or_duration_uses_default_assumptions():
    context = build_conversation_context("帮我规划一份灵山胜境导游路线", [])

    assert context.needs_clarification is False
    assert context.clarifying_question == ""
    assert "普通游客" in context.assumptions
    assert "正常体力" in context.assumptions


def test_route_planning_with_chinese_duration_does_not_ask_for_people():
    context = build_conversation_context(
        "我览灵山胜境，请帮我规划路线想用五小时游玩时",
        [],
        question_expander=QwenQuestionExpander(FakeExpansionClient(), model_name="qwen3.7-plus"),
    )

    assert context.needs_clarification is False
    assert context.clarifying_question == ""
    assert "灵山胜境五小时游览路线怎么安排" in context.expanded_questions
    assert context.selected_questions[0] == "灵山胜境五小时游览路线怎么安排"


def test_route_planning_with_chinese_count_word_duration_does_not_clarify():
    context = build_conversation_context(
        "想用五个小时玩灵山胜境",
        [],
        question_expander=QwenQuestionExpander(FakeExpansionClient(), model_name="qwen3.7-plus"),
    )

    assert context.needs_clarification is False
    assert any("五小时" in question for question in context.expanded_questions)


def test_short_how_to_play_question_uses_history_for_expansion():
    context = build_conversation_context(
        "怎么玩",
        [ConversationMessage(role="user", content="我想去灵山胜境游玩")],
        question_expander=QwenQuestionExpander(FakeExpansionClient(), model_name="qwen3.7-plus"),
    )

    assert context.needs_clarification is False
    assert context.standalone_question == "灵山胜境怎么玩"
    assert any("灵山胜境" in question and "路线" in question for question in context.expanded_questions)
    assert len(context.selected_questions) == 3


def test_weather_question_skips_model_expansion_when_target_is_clear():
    fake_client = FakeExpansionClient()

    context = build_conversation_context(
        "灵山胜境今日天气如何？",
        [],
        question_expander=QwenQuestionExpander(fake_client, model_name="qwen3.7-plus"),
    )

    assert fake_client.calls == 0
    assert context.expanded_questions == ["灵山胜境今日天气如何？"]
    assert context.selected_questions == ["灵山胜境今日天气如何？"]


def test_direct_route_question_skips_model_expansion_when_points_are_clear():
    fake_client = FakeExpansionClient()

    context = build_conversation_context(
        "从无锡站到灵山胜境怎么走？",
        [],
        question_expander=QwenQuestionExpander(fake_client, model_name="qwen3.7-plus"),
    )

    assert fake_client.calls == 0
    assert context.expanded_questions == ["从无锡站到灵山胜境怎么走？"]
    assert context.selected_questions == ["从无锡站到灵山胜境怎么走？"]


def test_follow_up_ticket_question_keeps_model_expansion():
    fake_client = FakeExpansionClient()

    build_conversation_context(
        "那门票呢？",
        [ConversationMessage(role="user", content="灵山胜境有什么特色？")],
        question_expander=QwenQuestionExpander(fake_client, model_name="qwen3.7-plus"),
    )

    assert fake_client.calls == 1


def test_history_is_trimmed_and_message_content_is_capped():
    long_content = "灵山胜境" + ("很适合游玩" * 200)
    history = [ConversationMessage(role="user", content=f"第{index}轮 {long_content}") for index in range(14)]

    context = build_conversation_context("那门票呢？", history)

    assert len(context.history) == 12
    assert all(len(message.content) <= 800 for message in context.history)
