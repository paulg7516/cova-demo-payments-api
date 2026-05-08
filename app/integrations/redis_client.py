"""Redis client used as a per-user notification queue + de-dup cache."""
import os

import redis.asyncio as redis_async

_client: redis_async.Redis | None = None


def get_redis() -> redis_async.Redis:
    global _client
    if _client is None:
        _client = redis_async.from_url(os.environ["REDIS_URL"], decode_responses=True)
    return _client


async def queue_notification(user_id: str, payload: dict) -> int:
    r = get_redis()
    return await r.lpush(f"notif:queue:{user_id}", str(payload))


async def already_sent(idempotency_key: str) -> bool:
    r = get_redis()
    added = await r.set(f"notif:sent:{idempotency_key}", "1", ex=86400, nx=True)
    return not added
