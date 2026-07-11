from pathlib import Path
import json

from lingjing_ai.config.settings import AppSettings
from lingjing_ai.rag.embeddings import HashingEmbeddingProvider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.rag.question_type import classify_question
from lingjing_ai.storage.vector_store import JsonVectorStore


def build_pipeline(tmp_path: Path) -> RagPipeline:
    settings = AppSettings.for_workspace(tmp_path)
    pipeline = RagPipeline(
        settings=settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
        vector_store=JsonVectorStore(tmp_path / "vectors.json"),
        answer_generator=ExtractiveAnswerGenerator(),
    )
    pipeline.ingest_uploaded_text(
        "灵境山综合资料.md",
        """
        # 灵境山综合资料

        ## 票务信息
        灵境山成人票价为 80 元，学生可凭证享受优惠。

        ## 游览服务
        ### 老人服务
        古栈道沿途设有休息点，游客服务中心提供轮椅咨询。

        ## 交通路线
        自驾游客可先到东门停车场，再沿湖畔栈桥前往古栈道入口。
        """,
    )
    return pipeline


def test_rag_eval_cases_hit_expected_documents_keywords_and_categories(tmp_path: Path):
    pipeline = build_pipeline(tmp_path)
    cases = json.loads(Path("tests/fixtures/rag_eval_cases.json").read_text(encoding="utf-8"))

    for case in cases:
        result = pipeline.ask(case["question"])

        assert classify_question(case["question"]).category == case["expected_category"]
        assert result.is_answered is True
        assert result.sources[0].document_name == case["expected_document"]
        assert case["expected_keyword"] in result.answer
