"""Redis-backed token usage and budget enforcement."""

import time
from dataclasses import dataclass

from fastapi import HTTPException
from redis import Redis


PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006
RETENTION_SECONDS = 45 * 24 * 60 * 60


@dataclass
class UsageSnapshot:
    month: str
    total_cost_usd: float
    request_count: int
    input_tokens: int
    output_tokens: int
    budget_remaining_usd: float


class RedisCostGuard:
    def __init__(
        self,
        redis_client: Redis,
        monthly_budget_usd: float,
        key_prefix: str = "usage",
    ) -> None:
        self.redis = redis_client
        self.monthly_budget_usd = monthly_budget_usd
        self.key_prefix = key_prefix

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS
        output_cost = (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
        return round(input_cost + output_cost, 6)

    def _month(self) -> str:
        return time.strftime("%Y-%m")

    def _global_key(self, month: str) -> str:
        return f"{self.key_prefix}:{month}:global"

    def _user_key(self, month: str, user_id: str) -> str:
        return f"{self.key_prefix}:{month}:user:{user_id}"

    def get_global_cost(self) -> float:
        month = self._month()
        raw_cost = self.redis.hget(self._global_key(month), "cost_usd")
        return float(raw_cost) if raw_cost else 0.0

    def check_budget(self, projected_input_tokens: int, projected_output_tokens: int) -> None:
        current_cost = self.get_global_cost()
        projected_cost = self.estimate_cost(projected_input_tokens, projected_output_tokens)

        if current_cost + projected_cost > self.monthly_budget_usd:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Monthly budget exceeded",
                    "budget_usd": self.monthly_budget_usd,
                    "current_cost_usd": round(current_cost, 6),
                    "projected_request_cost_usd": projected_cost,
                },
            )

    def record_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> UsageSnapshot:
        month = self._month()
        cost_usd = self.estimate_cost(input_tokens, output_tokens)
        global_key = self._global_key(month)
        user_key = self._user_key(month, user_id)

        pipeline = self.redis.pipeline()
        pipeline.hincrby(global_key, "request_count", 1)
        pipeline.hincrby(global_key, "input_tokens", input_tokens)
        pipeline.hincrby(global_key, "output_tokens", output_tokens)
        pipeline.hincrbyfloat(global_key, "cost_usd", cost_usd)
        pipeline.expire(global_key, RETENTION_SECONDS)

        pipeline.hincrby(user_key, "request_count", 1)
        pipeline.hincrby(user_key, "input_tokens", input_tokens)
        pipeline.hincrby(user_key, "output_tokens", output_tokens)
        pipeline.hincrbyfloat(user_key, "cost_usd", cost_usd)
        pipeline.expire(user_key, RETENTION_SECONDS)
        pipeline.execute()

        return self.get_usage(user_id)

    def get_usage(self, user_id: str) -> UsageSnapshot:
        month = self._month()
        user_key = self._user_key(month, user_id)
        raw = self.redis.hgetall(user_key)
        total_cost_usd = float(raw.get("cost_usd", 0.0))
        request_count = int(raw.get("request_count", 0))
        input_tokens = int(raw.get("input_tokens", 0))
        output_tokens = int(raw.get("output_tokens", 0))
        return UsageSnapshot(
            month=month,
            total_cost_usd=round(total_cost_usd, 6),
            request_count=request_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            budget_remaining_usd=round(max(0.0, self.monthly_budget_usd - total_cost_usd), 6),
        )
