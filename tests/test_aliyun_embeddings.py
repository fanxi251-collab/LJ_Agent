import httpx
import pytest

from lingjing_ai.rag.embeddings import AliyunEmbeddingError, AliyunEmbeddingProvider


class FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad response", request=httpx.Request("POST", "https://example.test"), response=httpx.Response(self.status_code))

    def json(self) -> dict:
        return self._payload


def test_aliyun_embedding_provider_parses_openai_compatible_response(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(
            200,
            {
                "data": [
                    {
                        "embedding": [0.1, 0.2, 0.3],
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = AliyunEmbeddingProvider(
        api_key="test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="text-embedding-v4",
        dimensions=3,
        timeout_seconds=12,
    )

    vector = provider.embed("灵境山有什么特色？")

    assert vector == [0.1, 0.2, 0.3]
    assert calls[0]["url"].endswith("/embeddings")
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0]["json"] == {
        "model": "text-embedding-v4",
        "input": "灵境山有什么特色？",
        "dimensions": 3,
    }
    assert calls[0]["timeout"] == 12


def test_aliyun_embedding_provider_raises_clear_error_on_bad_response(monkeypatch):
    def fake_post(url, headers, json, timeout):
        return FakeResponse(200, {"data": [{}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = AliyunEmbeddingProvider(
        api_key="test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="text-embedding-v4",
        dimensions=3,
    )

    with pytest.raises(AliyunEmbeddingError, match="embedding 响应格式异常"):
        provider.embed("测试")


def test_aliyun_embedding_provider_returns_zero_vector_for_empty_text(monkeypatch):
    def fake_post(url, headers, json, timeout):
        raise AssertionError("empty text should not call remote API")

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = AliyunEmbeddingProvider(
        api_key="test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="text-embedding-v4",
        dimensions=3,
    )

    assert provider.embed("   ") == [0.0, 0.0, 0.0]
