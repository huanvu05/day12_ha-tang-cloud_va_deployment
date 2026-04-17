"""Environment-driven settings for the Day 12 final project."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env.local", override=False)
load_dotenv(BASE_DIR / ".env", override=False)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class Settings:
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Day 12 Production Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))

    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "mock-llm"))

    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    allowed_origins: list[str] = field(
        default_factory=lambda: _split_csv(os.getenv("ALLOWED_ORIGINS", "*"))
    )

    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    )
    rate_limit_window_seconds: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    )

    monthly_budget_usd: float = field(
        default_factory=lambda: float(
            os.getenv("MONTHLY_BUDGET_USD", os.getenv("DAILY_BUDGET_USD", "10.0"))
        )
    )

    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    history_max_messages: int = field(
        default_factory=lambda: int(os.getenv("HISTORY_MAX_MESSAGES", "20"))
    )
    history_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("HISTORY_TTL_SECONDS", "86400"))
    )
    graceful_shutdown_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS", "30"))
    )

    def validate(self) -> "Settings":
        logger = logging.getLogger(__name__)
        if not self.agent_api_key:
            raise ValueError("AGENT_API_KEY must be set via environment variables.")
        if not self.redis_url:
            raise ValueError("REDIS_URL must be set via environment variables.")
        if not self.allowed_origins:
            self.allowed_origins = ["*"]
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set; falling back to mock LLM.")
        return self


settings = Settings().validate()
