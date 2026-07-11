from collections import Counter
import hashlib
import math
import re

import httpx


class AliyunEmbeddingError(RuntimeError):
    pass


class AliyunEmbeddingProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        dimensions: int,
        timeout_seconds: int = 30,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds

    def embed(self, text: str) -> list[float]:
        cleaned = text.strip()
        if not cleaned:
            # 空文本没有语义信息，直接返回零向量可以避免一次无意义的远端 API 调用。
            return [0.0] * self.dimensions

        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": cleaned,
                    "dimensions": self.dimensions,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            embedding = payload["data"][0]["embedding"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise AliyunEmbeddingError(f"embedding 响应格式异常或调用失败：{exc}") from exc

        if not isinstance(embedding, list) or not all(isinstance(value, int | float) for value in embedding):
            raise AliyunEmbeddingError("embedding 响应格式异常：embedding 必须是数字数组")
        return [float(value) for value in embedding]


class HashingEmbeddingProvider:
    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = self._tokens(text)
        if not tokens:
            return vector

        counts = Counter(tokens)
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * float(count)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def _tokens(self, text: str) -> list[str]:
        lowered = text.lower()
        words = re.findall(r"[a-z0-9]+", lowered)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
        chinese_bigrams = [
            "".join(chinese_chars[index : index + 2])
            for index in range(0, max(0, len(chinese_chars) - 1))
        ]
        return words + chinese_chars + chinese_bigrams
