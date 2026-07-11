from lingjing_ai.models.rag import SourceChunk
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator, QwenAnswerGenerator
from lingjing_ai.rag.llm_client import LlmCallError


class FakeLlmClient:
    def __init__(self) -> None:
        self.messages = None

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.messages = messages
        return "灵境山以云海日出和古栈道闻名。"

    def chat_stream(self, messages: list[dict[str, str]]):
        self.messages = messages
        yield "灵境山"
        yield "以云海日出"
        yield "和古栈道闻名。"


def test_qwen_generator_uses_sources_and_question_in_prompt():
    client = FakeLlmClient()
    system_prompt = "系统提示：只能依据提供的景区资料回答，禁止编造，并给出来源依据。"
    generator = QwenAnswerGenerator(client, system_prompt=system_prompt)
    source = SourceChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        document_name="灵境山资料.md",
        content="灵境山位于青岚湖东岸，以云海日出和古栈道闻名。",
        score=0.86,
    )

    answer = generator.generate("灵境山有什么特色？", [source])

    assert "### 简要回答" in answer
    assert "灵境山以云海日出和古栈道闻名。" in answer
    assert "依据：灵境山资料.md" in answer
    assert client.messages is not None
    assert client.messages[0]["content"] == system_prompt
    assert "灵境山有什么特色？" in client.messages[1]["content"]
    assert "灵境山资料.md" in client.messages[1]["content"]
    assert "回答要求" in client.messages[1]["content"]
    assert "不要输出资料之外的景区事实" in client.messages[1]["content"]
    assert "### 简要回答" in client.messages[1]["content"]
    assert "### 详细说明" in client.messages[1]["content"]
    assert "### 温馨提示" in client.messages[1]["content"]
    assert "依据：资料名称" in client.messages[1]["content"]


def test_qwen_generator_refuses_without_sources_and_does_not_call_model():
    client = FakeLlmClient()
    generator = QwenAnswerGenerator(client)

    answer = generator.generate("熊猫馆开放时间是什么？", [])

    assert "当前资料中没有查到可靠依据" in answer
    assert client.messages is None


class FailingLlmClient:
    def chat(self, messages: list[dict[str, str]]) -> str:
        raise LlmCallError("Qwen API request failed: timed out")

    def chat_stream(self, messages: list[dict[str, str]]):
        raise LlmCallError("Qwen API request failed: timed out")


class PartialFailingLlmClient:
    def chat(self, messages: list[dict[str, str]]) -> str:
        return "不会被调用"

    def chat_stream(self, messages: list[dict[str, str]]):
        yield "### 简要回答\n已输出的模型回答。"
        raise LlmCallError("stream interrupted")


class RigidRouteLlmClient:
    def __init__(self) -> None:
        self.messages = None

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.messages = messages
        return (
            "### 简要回答\n"
            "当前资料中没有查到具体的游玩路线（如起点、顺序等），暂时无法为您确认详细的适老路线。"
            "不过资料中提到景区内有观光车，非常适合体力有限的老人乘坐游览。\n\n"
            "### 详细说明\n"
            "- 资料中未明确说明路线顺序。\n\n"
            "### 温馨提示\n"
            "建议以景区公告为准。\n\n"
            "依据：灵境山资料.md"
        )

    def chat_stream(self, messages: list[dict[str, str]]):
        self.messages = messages
        yield self.chat(messages)


def test_qwen_generator_falls_back_to_extract_answer_when_model_fails():
    generator = QwenAnswerGenerator(FailingLlmClient())
    source = SourceChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        document_name="灵山胜境游览指南.md",
        content="灵山胜境以灵山大佛、九龙灌浴和梵宫文化体验闻名。",
        score=0.86,
    )

    answer = generator.generate("灵山胜境有什么特色？", [source])

    assert "根据景区资料" in answer
    assert "灵山大佛" in answer
    assert "\n## " not in answer
    assert "|" not in answer


def test_qwen_generator_streams_normalized_model_answer():
    client = FakeLlmClient()
    generator = QwenAnswerGenerator(client)
    source = SourceChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        document_name="灵境山资料.md",
        content="灵境山位于青岚湖东岸，以云海日出和古栈道闻名。",
        score=0.86,
    )

    answer = "".join(generator.generate_stream("灵境山有什么特色？", [source]))

    assert "### 简要回答" in answer
    assert "灵境山以云海日出和古栈道闻名。" in answer
    assert "依据：灵境山资料.md" in answer
    assert client.messages is not None


def test_qwen_generator_stream_falls_back_to_extract_answer_when_model_fails():
    generator = QwenAnswerGenerator(FailingLlmClient())
    source = SourceChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        document_name="灵山胜境游览指南.md",
        content="灵山胜境以灵山大佛、九龙灌浴和梵宫文化体验闻名。",
        score=0.86,
    )

    answer = "".join(generator.generate_stream("灵山胜境有什么特色？", [source]))

    assert "根据景区资料" in answer
    assert "灵山大佛" in answer


def test_qwen_generator_stream_does_not_append_extract_answer_after_partial_output():
    generator = QwenAnswerGenerator(PartialFailingLlmClient())
    source = SourceChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        document_name="灵山胜境游览指南.md",
        content="## 原始标题\n| 网购联票 | 225元 |\n灵山胜境以灵山大佛闻名。",
        score=0.86,
    )

    answer = "".join(generator.generate_stream("灵山胜境有什么特色？", [source]))

    assert "已输出的模型回答" in answer
    assert "灵山胜境以灵山大佛闻名" not in answer
    assert "网购联票" not in answer


def test_qwen_generator_softens_rigid_route_refusal_when_sources_support_suggestions():
    client = RigidRouteLlmClient()
    generator = QwenAnswerGenerator(client)
    source = SourceChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        document_name="灵境山资料.md",
        content="景区内有观光车，适合体力有限的老人乘坐游览。古栈道沿途设有休息点。",
        score=0.86,
        metadata={"category": "服务设施"},
    )

    answer = generator.generate("帮我规划一份适合老人的导游路线", [source])

    assert "可以按“少步行、观光车优先、适当休息”的思路规划" in answer
    assert "观光车" in answer
    assert "休息点" in answer
    assert "暂时无法为您确认详细的适老路线" not in answer
    assert "资料未提供完整的起点和游览顺序" in answer
    assert "依据：灵境山资料.md" in answer
    assert client.messages is not None
    assert "如果游客是在请你规划路线" in client.messages[1]["content"]


def test_extractive_generator_gives_route_suggestion_from_partial_route_evidence():
    generator = ExtractiveAnswerGenerator()
    source = SourceChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        document_name="灵境山资料.md",
        content="景区内有观光车，适合体力有限的老人乘坐游览。古栈道沿途设有休息点。",
        score=0.86,
        metadata={"category": "服务设施"},
    )

    answer = generator.generate("帮我规划一份适合老人的导游路线", [source])

    assert "观光车优先" in answer
    assert "休息点" in answer
    assert "资料未提供完整的起点和游览顺序" in answer


def test_extractive_generator_uses_weather_template_for_amap_weather_source():
    generator = ExtractiveAnswerGenerator()
    weather_source = SourceChunk(
        chunk_id="amap_weather_无锡",
        document_id="amap_weather",
        document_name="高德天气",
        content="无锡当前天气阴，气温27℃，东南风3级，湿度70%，发布时间2026-07-08 09:00:00。",
        score=1.0,
        metadata={
            "source_type": "amap_weather",
            "city": "无锡",
            "weather": "阴",
            "temperature": "27",
            "winddirection": "东南",
            "windpower": "3",
            "humidity": "70",
            "reporttime": "2026-07-08 09:00:00",
        },
    )
    scenic_source = SourceChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        document_name="灵山胜境资料.md",
        content="灵山胜境坐落于江苏省无锡市太湖西北部，是国家5A级旅游景区。",
        score=0.95,
    )

    answer = generator.generate("灵山胜境今日的天气如何？", [weather_source, scenic_source])

    assert "### 简要回答" in answer
    assert "无锡当前天气阴" in answer
    assert "- 天气：阴" in answer
    assert "- 气温：27℃" in answer
    assert "国家5A级旅游景区" not in answer
    assert "依据：高德天气" in answer


def test_extractive_generator_uses_structured_answer_format():
    generator = ExtractiveAnswerGenerator()
    source = SourceChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        document_name="灵境山资料.md",
        content="灵境山以云海日出和古栈道闻名。",
        score=0.86,
    )

    answer = generator.generate("灵境山有什么特色？", [source])

    assert "### 简要回答" in answer
    assert "### 详细说明" in answer
    assert "依据：灵境山资料.md" in answer


def test_extractive_generator_cleans_markdown_noise():
    generator = ExtractiveAnswerGenerator()
    source = SourceChunk(
        chunk_id="chunk_1",
        document_id="doc_1",
        document_name="灵山胜境游览指南.md",
        content="## 2. 最佳游览时间\n| 网购联票 | 225元 |\n**九龙灌浴**每日4-5场。",
        score=0.86,
    )

    answer = generator.generate("灵山胜境有什么表演？", [source])

    assert "\n## " not in answer
    assert "|" not in answer
    assert "**" not in answer
