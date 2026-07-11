from __future__ import annotations

import json
from typing import Iterator, Protocol
from urllib import request, error


class LlmClient(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str:
        ...

    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        ...


class LlmCallError(RuntimeError):
    pass


class AliyunQwenClient:
    def __init__(
        self,
        api_key: str,
        model: str = "qwen3.7-max",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout_seconds: int = 30,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def chat(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        http_request = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LlmCallError(f"Qwen API HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise LlmCallError(f"Qwen API request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LlmCallError("Qwen API request timed out") from exc

        data = json.loads(raw_body)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmCallError(f"Unexpected Qwen API response: {raw_body}") from exc

    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "stream": True,
        }
        http_request = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_text = line.removeprefix("data:").strip()
                    if data_text == "[DONE]":
                        break
                    try:
                        data = json.loads(data_text)
                        content = data["choices"][0].get("delta", {}).get("content", "")
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                        raise LlmCallError(f"Unexpected Qwen stream response: {data_text}") from exc
                    if content:
                        yield content
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LlmCallError(f"Qwen API HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise LlmCallError(f"Qwen API request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LlmCallError("Qwen API request timed out") from exc
