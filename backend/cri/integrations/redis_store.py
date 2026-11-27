"""Redis primitives for short-lived cache, queues and agent heartbeats."""
import json
import time

class RedisTTLStore:
    @classmethod
    def from_url(cls, url=None, prefix="cri:", **kwargs):
        import os
        target = url or os.getenv("CRI_REDIS_URL") or os.getenv("REDIS_URL")
        if not target:
            raise ValueError("Redis URL is required")
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("redis package is required") from exc
        client = redis.Redis.from_url(target, decode_responses=True, socket_connect_timeout=3, socket_timeout=5, **kwargs)
        client.ping()
        return cls(client, prefix)
    def __init__(self, client, prefix="cri:"):
        self.client, self.prefix = client, prefix
    def _key(self, key):
        if not isinstance(key, str) or not key or len(key) > 200:
            raise ValueError("invalid key")
        return self.prefix + key
    def put(self, key: str, value, ttl_seconds: int = 3600):
        if not 1 <= ttl_seconds <= 604800:
            raise ValueError("invalid TTL")
        try:
            encoded = json.dumps(value, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("value must be JSON serializable") from exc
        self.client.setex(self._key(key), ttl_seconds, encoded)
    def get(self, key: str):
        raw = self.client.get(self._key(key))
        if raw is None: return None
        if isinstance(raw, bytes): raw = raw.decode("utf-8")
        return json.loads(raw)
    def delete(self, key: str):
        return bool(self.client.delete(self._key(key)))
    def enqueue(self, queue: str, value: dict, max_length: int = 10000):
        if not isinstance(value, dict) or not 1 <= max_length <= 100000:
            raise ValueError("invalid queue payload or bound")
        key = self._key("queue:" + queue)
        self.client.rpush(key, json.dumps(value, separators=(",", ":"), allow_nan=False))
        self.client.ltrim(key, -max_length, -1)
        return self.client.llen(key)
    def dequeue(self, queue: str, timeout: int = 1):
        if not 0 <= timeout <= 30: raise ValueError("timeout out of range")
        item = self.client.blpop(self._key("queue:" + queue), timeout=timeout)
        if item is None: return None
        raw = item[1]
        if isinstance(raw, bytes): raw = raw.decode("utf-8")
        return json.loads(raw)
    def heartbeat(self, agent_id: str, state: dict, ttl_seconds: int = 60):
        state = dict(state); state["heartbeat_at"] = time.time()
        self.put("agents:" + agent_id, state, ttl_seconds)
    def agent_state(self, agent_id: str):
        return self.get("agents:" + agent_id)
