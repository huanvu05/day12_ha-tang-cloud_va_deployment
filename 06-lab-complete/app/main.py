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
from app.config import Settings
from app.cost_guard import RedisCostGuard
from app.rate_limiter import RedisRateLimiter
from utils.mock_llm import ask as llm_ask


# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
    force=True,
)
logger = logging.getLogger("day12.agent")

START_TIME = time.time()

# =========================
# SETTINGS (FIX CRASH HERE)
# =========================
# ❌ OLD: settings = Settings().validate()
# ✅ NEW: lazy validate inside startup
settings = Settings()


# =========================
# GLOBAL STATE
# =========================
redis_client = None
rate_limiter = None
cost_guard = None

_is_ready = False
_shutdown_requested = False
_request_count = 0
_error_count = 0
_active_requests = 0


# =========================
# REDIS INIT SAFE
# =========================
def init_redis():
    global redis_client, rate_limiter, cost_guard, _is_ready

    try:
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        redis_client.ping()

        rate_limiter = RedisRateLimiter(
            redis_client=redis_client,
            max_requests=settings.rate_limit_per_minute,
            window_seconds=settings.rate_limit_window_seconds,
        )

        cost_guard = RedisCostGuard(
            redis_client=redis_client,
            monthly_budget_usd=settings.monthly_budget_usd,
        )

        _is_ready = True
        logger.info(json.dumps({"event": "redis_connected"}))

    except Exception as e:
        # ⚠️ FIX: không crash app
        _is_ready = False
        redis_client = None
        logger.error(json.dumps({"event": "redis_unavailable", "error": str(e)}))


# =========================
# HELPERS
# =========================
def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def estimate_tokens(text: str):
    return max(1, len(text.split()) * 2)


def history_key(uid: str):
    return f"history:{uid}"


def load_history(uid: str):
    if not redis_client:
        return []

    try:
        raw = redis_client.lrange(history_key(uid), 0, -1)
        return [json.loads(x) for x in raw]
    except:
        return []


def append_history(uid: str, role: str, content: str):
    if not redis_client:
        return

    try:
        redis_client.rpush(
            history_key(uid),
            json.dumps({
                "role": role,
                "content": content,
                "ts": utc_now_iso()
            })
        )
    except Exception as e:
        logger.error(json.dumps({"event": "history_error", "error": str(e)}))


# =========================
# AGENT LOGIC
# =========================
def build_answer(question: str, history: list[dict]):
    q = question.lower()

    if "last question" in q:
        for m in reversed(history):
            if m["role"] == "user":
                return f"Last question: {m['content']}"

    return llm_ask(question)


# =========================
# LIFESPAN
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(json.dumps({"event": "startup"}))

    # ⚠️ FIX: validate HERE not at import time
    try:
        settings.validate()
    except Exception as e:
        logger.error(json.dumps({"event": "config_invalid", "error": str(e)}))

    init_redis()

    yield

    logger.info(json.dumps({"event": "shutdown"}))


# =========================
# FASTAPI APP
# =========================
app = FastAPI(
    title="Day 12 Production Agent",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# MIDDLEWARE
# =========================
@app.middleware("http")
async def middleware(request: Request, call_next):
    if request.url.path in ["/ask", "/metrics"]:
        try:
            verify_api_key_value(request.headers.get("X-API-Key"))
        except Exception as e:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "detail": str(e)}
            )

    return await call_next(request)


# =========================
# MODELS
# =========================
class AskRequest(BaseModel):
    user_id: str
    question: str


# =========================
# ROUTES
# =========================
@app.get("/health")
def health():
    return {
        "status": "ok" if _is_ready else "degraded",
        "uptime": round(time.time() - START_TIME, 2),
        "redis": bool(redis_client)
    }


@app.post("/ask")
def ask(req: AskRequest):
    history = load_history(req.user_id)

    append_history(req.user_id, "user", req.question)

    answer = build_answer(req.question, history)

    append_history(req.user_id, "assistant", answer)

    return {
        "answer": answer,
        "user_id": req.user_id,
        "history": len(history)
    }


@app.get("/")
def root():
    return {"status": "running"}


# =========================
# RUN
# =========================
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=10000)