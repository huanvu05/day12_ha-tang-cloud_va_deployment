"""Redis-backed per-user sliding window rate limiting."""

import math
import time
from dataclasses import dataclass

from fastapi import HTTPException
from redis import Redis


@dataclass
class RateLimitResult:
    limit: int
    remaining: int
    reset_at: int
    retry_after: int | None = None


class RedisRateLimiter:
    def __init__(
        self,
        redis_client: Redis,
        max_requests: int,
        window_seconds: int = 60,
        key_prefix: str = "rate_limit",
    ) -> None:
        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix

    def _key(self, user_id: str) -> str:
        return f"{self.key_prefix}:{user_id}"

    def check(self, user_id: str) -> RateLimitResult:
        """Check and record a request for a user."""
        now = time.time()
        window_start = now - self.window_seconds
        key = self._key(user_id)

        pipeline = self.redis.pipeline()
        pipeline.zremrangebyscore(key, 0, window_start)
        pipeline.zcard(key)
        pipeline.zrange(key, 0, 0, withscores=True)
        _, current_count, oldest_entries = pipeline.execute()

        reset_at = math.ceil(now + self.window_seconds)

        if current_count >= self.max_requests:
            oldest_score = oldest_entries[0][1] if oldest_entries else now
            retry_after = max(1, math.ceil(oldest_score + self.window_seconds - now))
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": self.max_requests,
                    "window_seconds": self.window_seconds,
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                },
            )

        member = f"{time.time_ns()}"
        pipeline = self.redis.pipeline()
        pipeline.zadd(key, {member: now})
        pipeline.expire(key, self.window_seconds)
        pipeline.execute()

        return RateLimitResult(
            limit=self.max_requests,
            remaining=max(0, self.max_requests - current_count - 1),
            reset_at=reset_at,
        )
