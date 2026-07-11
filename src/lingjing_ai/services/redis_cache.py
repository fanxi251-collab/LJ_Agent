from __future__ import annotations

import json
from typing import Any


class RedisJsonCache:
    def __init__(self, enabled: bool, prefix: str, client: Any | None = None) -> None:
        self.enabled = enabled
        self.prefix = prefix.strip(":") or "lingjing"
        self.client = client

    @classmethod
    def from_url(cls, enabled: bool, redis_url: str, prefix: str) -> "RedisJsonCache":
        if not enabled or not redis_url:
            return cls(enabled=False, prefix=prefix)
        try:
            import redis

            client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
            client.ping()
        except Exception:
            return cls(enabled=False, prefix=prefix)
        return cls(enabled=True, prefix=prefix, client=client)

    def get_json(self, key: str) -> dict | None:
        if not self._is_available():
            return None
        try:
            raw_value = self.client.get(self._key(key))
            if raw_value is None:
                return None
            if isinstance(raw_value, bytes):
                raw_value = raw_value.decode("utf-8")
            value = json.loads(raw_value)
            return value if isinstance(value, dict) else None
        except Exception:
            return None

    def set_json(self, key: str, value: dict, ttl_seconds: int) -> None:
        if not self._is_available() or ttl_seconds <= 0:
            return
        try:
            self.client.setex(
                self._key(key),
                ttl_seconds,
                json.dumps(value, ensure_ascii=False),
            )
        except Exception:
            return

    def delete(self, key: str) -> None:
        if not self._is_available():
            return
        try:
            self.client.delete(self._key(key))
        except Exception:
            return

    def clear_prefix(self, prefix: str = "") -> None:
        if not self._is_available():
            return
        pattern = self._key(f"{prefix}*")
        try:
            for key in self.client.scan_iter(match=pattern):
                self.client.delete(key)
        except Exception:
            return

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    def _is_available(self) -> bool:
        return bool(self.enabled and self.client is not None)
