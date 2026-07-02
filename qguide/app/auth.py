"""
JWT auth helpers for the Q-Guide API.

Stateless bearer tokens (HS256). The signing key comes from the JWT_SECRET env var;
a development fallback is used locally (never deploy without setting JWT_SECRET).
"""
from __future__ import annotations

import os
import time
from typing import Optional

import jwt

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-change-me")
JWT_ALGO = "HS256"
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7   # 7 days


def make_token(email: str) -> str:
    now = int(time.time())
    payload = {"sub": email, "iat": now, "exp": now + TOKEN_TTL_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> Optional[str]:
    """Return the email (sub) for a valid token, else None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
