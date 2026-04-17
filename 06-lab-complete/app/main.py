"""Production-ready AI agent for the Day 12 final project."""

import asyncio
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key, verify_api_key_value
from app.config import settings
from app.cost_guard import RedisCostGuard
from app.rate_limiter import RedisRateLimiter
from utils.mock_llm import ask as llm_ask


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
    force=True,
)
logger = logging.getLogger("day12.agent")

START_TIME = time.time()
redis_client = redis.from_url(settings.redis_url, decode_responses=True)
rate_limiter = RedisRateLimiter(
    redis_client=redis_client,
    max_requests=settings.rate_limit_per_minute,
    window_seconds=settings.rate_limit_window_seconds,
)
cost_guard = RedisCostGuard(
    redis_client=redis_client,
    monthly_budget_usd=settings.monthly_budget_usd,
)

_is_ready = False
_shutdown_requested = False
_request_count = 0
_error_count = 0
_active_requests = 0


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()) * 2)


def history_key(user_id: str) -> str:
    return f"history:{user_id}"


def load_history(user_id: str) -> list[dict]:
    raw_messages = redis_client.lrange(history_key(user_id), 0, -1)
    messages: list[dict] = []
    for item in raw_messages:
        try:
            messages.append(json.loads(item))
        except json.JSONDecodeError:
            continue
    return messages


def append_to_history(user_id: str, role: str, content: str) -> None:
    message = json.dumps(
        {
            "role": role,
            "content": content,
            "timestamp": utc_now_iso(),
        }
    )
    pipeline = redis_client.pipeline()
    pipeline.rpush(history_key(user_id), message)
    pipeline.ltrim(history_key(user_id), -settings.history_max_messages, -1)
    pipeline.expire(history_key(user_id), settings.history_ttl_seconds)
    pipeline.execute()


def extract_known_name(history: list[dict]) -> str | None:
    pattern = re.compile(r"\bmy name is ([A-Za-z][A-Za-z0-9_-]{0,49})\b", re.IGNORECASE)
    for message in reversed(history):
        if message.get("role") != "user":
            continue
        match = pattern.search(message.get("content", ""))
        if match:
            return match.group(1)
    return None


def build_agent_answer(question: str, history: list[dict]) -> str:
    normalized = question.strip().lower()

    if "what is my name" in normalized or "remember my name" in normalized:
        known_name = extract_known_name(history)
        if known_name:
            return f"Your name is {known_name}. I retrieved it from Redis-backed conversation history."

    if "what was my last question" in normalized or "what did i ask before" in normalized:
        previous_user_messages = [
            item.get("content", "")
            for item in history
            if item.get("role") == "user" and item.get("content")
        ]
        if previous_user_messages:
            return f"Your previous question was: {previous_user_messages[-1]}"

    answer = llm_ask(question)
    prior_turns = len([item for item in history if item.get("role") == "user"])
    if prior_turns:
        return f"{answer} Context remembered: {prior_turns} prior user turn(s)."
    return answer


def redis_ready() -> bool:
    try:
        redis_client.ping()
        return True
    except redis.exceptions.RedisError:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready, _shutdown_requested

    logger.info(
        json.dumps(
            {
                "event": "startup",
                "app": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
            }
        )
    )

    _shutdown_requested = False
    _is_ready = redis_ready()
    if _is_ready:
        logger.info(json.dumps({"event": "redis_connected"}))
    else:
        logger.error(json.dumps({"event": "redis_unavailable"}))

    yield

    _shutdown_requested = True
    _is_ready = False
    logger.info(
        json.dumps(
            {
                "event": "graceful_shutdown_started",
                "active_requests": _active_requests,
            }
        )
    )
    deadline = time.time() + settings.graceful_shutdown_timeout_seconds
    while _active_requests > 0 and time.time() < deadline:
        await asyncio.sleep(0.1)
    redis_client.close()
    logger.info(
        json.dumps(
            {
                "event": "graceful_shutdown_completed",
                "remaining_active_requests": _active_requests,
            }
        )
    )


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _active_requests, _error_count, _request_count

    if _shutdown_requested and request.url.path not in {"/health"}:
        return JSONResponse(
            status_code=503,
            content={"error": "service_unavailable", "detail": "Service is shutting down."},
        )

    if request.url.path in {"/ask", "/metrics"}:
        try:
            verify_api_key_value(request.headers.get("X-API-Key"))
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": "authentication_error", "detail": exc.detail},
                headers=exc.headers or {},
            )

    start = time.time()
    _request_count += 1
    _active_requests += 1
    try:
        response: Response = await call_next(request)
    except Exception:
        _error_count += 1
        raise
    finally:
        _active_requests = max(0, _active_requests - 1)

    duration_ms = round((time.time() - start) * 1000, 1)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if "server" in response.headers:
        del response.headers["server"]

    logger.info(
        json.dumps(
            {
                "event": "request_completed",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }
        )
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception(json.dumps({"event": "unhandled_exception", "error": str(exc)}))
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "Unexpected server error.",
        },
    )


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    history_length: int
    monthly_cost_usd: float
    timestamp: str


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
):
    try:
        rate_limit = rate_limiter.check(body.user_id)
        input_tokens = estimate_tokens(body.question)
        projected_output_tokens = max(24, min(160, input_tokens))
        cost_guard.check_budget(
            projected_input_tokens=input_tokens,
            projected_output_tokens=projected_output_tokens,
        )
        history_before = load_history(body.user_id)
        append_to_history(body.user_id, "user", body.question)
    except redis.exceptions.RedisError as exc:
        logger.error(json.dumps({"event": "redis_error", "error": str(exc)}))
        raise HTTPException(status_code=503, detail="Redis is unavailable.")

    logger.info(
        json.dumps(
            {
                "event": "agent_call",
                "user_id": body.user_id,
                "client": request.client.host if request.client else "unknown",
                "question_length": len(body.question),
            }
        )
    )

    answer = build_agent_answer(body.question, history_before)
    output_tokens = estimate_tokens(answer)

    try:
        usage = cost_guard.record_usage(body.user_id, input_tokens, output_tokens)
        append_to_history(body.user_id, "assistant", answer)
        updated_history = load_history(body.user_id)
    except redis.exceptions.RedisError as exc:
        logger.error(json.dumps({"event": "redis_error", "error": str(exc)}))
        raise HTTPException(status_code=503, detail="Redis is unavailable.")

    response = AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        history_length=len(updated_history),
        monthly_cost_usd=usage.total_cost_usd,
        timestamp=utc_now_iso(),
    )

    json_response = JSONResponse(status_code=200, content=response.model_dump())
    json_response.headers["X-RateLimit-Limit"] = str(rate_limit.limit)
    json_response.headers["X-RateLimit-Remaining"] = str(rate_limit.remaining)
    json_response.headers["X-RateLimit-Reset"] = str(rate_limit.reset_at)
    return json_response


@app.get("/health", tags=["Operations"])
def health():
    connected = redis_ready()
    return {
        "status": "ok" if connected else "degraded",
        "version": settings.app_version,
        "environment": settings.environment,
        "redis": "connected" if connected else "disconnected",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "active_requests": _active_requests,
        "timestamp": utc_now_iso(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready or _shutdown_requested:
        raise HTTPException(status_code=503, detail="Service is not ready.")
    if not redis_ready():
        raise HTTPException(status_code=503, detail="Redis is not ready.")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(_: str = Depends(verify_api_key)):
    try:
        monthly_cost = cost_guard.get_global_cost()
    except redis.exceptions.RedisError as exc:
        logger.error(json.dumps({"event": "redis_error", "error": str(exc)}))
        raise HTTPException(status_code=503, detail="Redis is unavailable.")

    budget_used_pct = 0.0
    if settings.monthly_budget_usd:
        budget_used_pct = round(monthly_cost / settings.monthly_budget_usd * 100, 2)

    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "active_requests": _active_requests,
        "monthly_cost_usd": round(monthly_cost, 6),
        "monthly_budget_usd": settings.monthly_budget_usd,
        "budget_used_pct": budget_used_pct,
    }


if __name__ == "__main__":
    logger.info(
        json.dumps(
            {
                "event": "server_starting",
                "host": settings.host,
                "port": settings.port,
            }
        )
    )
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=int(settings.graceful_shutdown_timeout_seconds),
    )
