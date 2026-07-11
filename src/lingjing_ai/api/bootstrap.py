from pathlib import Path

from lingjing_ai.config.settings import AppSettings
from lingjing_ai.kg.factory import build_knowledge_graph_store
from lingjing_ai.rag.embedding_factory import build_embedding_provider
from lingjing_ai.rag.generator import ExtractiveAnswerGenerator, QwenAnswerGenerator
from lingjing_ai.rag.llm_client import AliyunQwenClient
from lingjing_ai.rag.pipeline import RagPipeline
from lingjing_ai.rag.prompt_loader import load_system_prompt
from lingjing_ai.storage.qdrant_vector_store import QdrantVectorStore


def build_default_pipeline() -> RagPipeline:
    return build_pipeline_components(AppSettings.for_workspace(Path.cwd()))


def build_pipeline_components(settings: AppSettings) -> RagPipeline:
    generator = ExtractiveAnswerGenerator()
    if settings.llm_api_key:
        client = AliyunQwenClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
        generator = QwenAnswerGenerator(
            client,
            system_prompt=load_system_prompt(settings.prompt_dir / "rag_system_prompt.md"),
        )

    vector_store = QdrantVectorStore(
        path=settings.qdrant_db_dir,
        collection_name=settings.vector_collection_name,
        vector_size=settings.embedding_dimensions,
    )
    pipeline = RagPipeline(
        settings=settings,
        embedding_provider=build_embedding_provider(settings),
        vector_store=vector_store,
        answer_generator=generator,
        knowledge_graph=build_knowledge_graph_store(settings),
    )
    print(
        "Qdrant active collection: "
        f"{vector_store.collection_name}, vector_size={settings.embedding_dimensions}, "
        f"migrated={getattr(vector_store, 'was_recreated', False)}"
    )
    if getattr(vector_store, "was_recreated", False):
        pipeline.rebuild_index_from_manifest()
    return pipeline
