from dataclasses import dataclass
import time

import redis

from backend.app.settings import Settings


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int


def check_generation_rate_limit(settings: Settings, user_id: str, limit_override: int | None = None) -> RateLimitResult:
    client = redis.Redis.from_url(settings.redis_url)
    minute_window = int(time.time() // 60)
    key = f"rate:generation:{user_id}:{minute_window}"

    with client.pipeline() as pipe:
        pipe.incr(key)
        pipe.expire(key, 70)
        count, _ = pipe.execute()

    limit = limit_override or settings.generation_rate_limit_per_minute
    remaining = max(limit - int(count), 0)
    reset_seconds = 60 - int(time.time() % 60)
    return RateLimitResult(
        allowed=int(count) <= limit,
        limit=limit,
        remaining=remaining,
        reset_seconds=reset_seconds,
    )


def get_generation_rate_limit_status(settings: Settings, user_id: str, limit: int) -> RateLimitResult:
    client = redis.Redis.from_url(settings.redis_url)
    minute_window = int(time.time() // 60)
    key = f"rate:generation:{user_id}:{minute_window}"
    count = int(client.get(key) or 0)
    remaining = max(limit - count, 0)
    reset_seconds = 60 - int(time.time() % 60)
    return RateLimitResult(
        allowed=count < limit,
        limit=limit,
        remaining=remaining,
        reset_seconds=reset_seconds,
    )
