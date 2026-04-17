"""API key authentication helpers."""

import secrets

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key_value(api_key: str | None) -> str:
    """Validate an API key value."""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include header: X-API-Key: <your-key>",
            headers={"WWW-Authenticate": "X-API-Key"},
        )

    if not secrets.compare_digest(api_key, settings.agent_api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "X-API-Key"},
        )

    return api_key


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """FastAPI dependency wrapper around API key validation."""
    return verify_api_key_value(api_key)
