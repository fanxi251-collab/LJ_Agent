import json

from lingjing_ai.services.redis_cache import RedisJsonCache


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def ping(self) -> bool:
        return True

    def get(self, key: str):
        return self.values.get(key)

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl_seconds

    def delete(self, key: str) -> None:
        self.values.pop(key, None)

    def scan_iter(self, match: str):
        prefix = match.removesuffix("*")
        for key in list(self.values):
            if key.startswith(prefix):
                yield key


class BrokenRedisClient(FakeRedisClient):
    def get(self, key: str):
        raise RuntimeError("redis down")

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        raise RuntimeError("redis down")


def test_redis_json_cache_round_trips_json_with_prefix_and_ttl():
    client = FakeRedisClient()
    cache = RedisJsonCache(enabled=True, prefix="lingjing", client=client)

    cache.set_json("answer:one", {"answer": "ok"}, ttl_seconds=30)

    assert client.ttls["lingjing:answer:one"] == 30
    assert json.loads(client.values["lingjing:answer:one"]) == {"answer": "ok"}
    assert cache.get_json("answer:one") == {"answer": "ok"}


def test_redis_json_cache_clear_prefix_deletes_matching_keys_only():
    client = FakeRedisClient()
    cache = RedisJsonCache(enabled=True, prefix="lingjing", client=client)
    cache.set_json("answer:one", {"value": 1}, ttl_seconds=30)
    cache.set_json("amap:weather:无锡", {"value": 2}, ttl_seconds=30)

    cache.clear_prefix("answer:")

    assert cache.get_json("answer:one") is None
    assert cache.get_json("amap:weather:无锡") == {"value": 2}


def test_redis_json_cache_swallows_redis_errors():
    cache = RedisJsonCache(enabled=True, prefix="lingjing", client=BrokenRedisClient())

    cache.set_json("answer:one", {"answer": "ok"}, ttl_seconds=30)

    assert cache.get_json("answer:one") is None
