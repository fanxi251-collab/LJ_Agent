from lingjing_ai.config.settings import AppSettings
from lingjing_ai.rag.embeddings import AliyunEmbeddingProvider, HashingEmbeddingProvider


def build_embedding_provider(settings: AppSettings):
    api_key = settings.embedding_api_key
    if settings.embedding_provider == "aliyun" and api_key:
        return AliyunEmbeddingProvider(
            api_key=api_key,
            base_url=settings.embedding_base_url,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return HashingEmbeddingProvider(dimensions=settings.embedding_dimensions)
