"""Redis TTL cache; callers inject a redis-py compatible client."""
import json
class RedisTTLStore:
    def __init__(self, client, prefix="cri:"):
        self.client, self.prefix = client, prefix
    def put(self, key: str, value: dict, ttl_seconds: int = 3600):
        if not key or len(key) > 200 or not 1 <= ttl_seconds <= 604800:
            raise ValueError("invalid key or TTL")
        self.client.setex(self.prefix + key, ttl_seconds, json.dumps(value, separators=(",", ":")))
    def get(self, key: str):
        raw = self.client.get(self.prefix + key)
        if raw is None: return None
        if isinstance(raw, bytes): raw = raw.decode("utf-8")
        return json.loads(raw)
    def delete(self, key: str):
        return bool(self.client.delete(self.prefix + key))
