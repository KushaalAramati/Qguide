"""
Lightweight in-process rate limiting for authentication endpoints.

Scope and honesty: this is a per-process, in-memory limiter. It raises the cost of
online password guessing on a single-instance deployment (the current Render
setup) but it is NOT a distributed limiter -- with multiple workers each has its
own window. If the deployment is scaled out, back this with Redis or the database
and keep the same interface.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, Tuple

_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = {}


def check(key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
    """Record an attempt for `key`. Returns (allowed, retry_after_seconds)."""
    now = time.time()
    with _lock:
        q = _hits.setdefault(key, deque())
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry = int(window_seconds - (now - q[0])) + 1
            return False, max(retry, 1)
        q.append(now)
        return True, 0


def reset(key: str) -> None:
    """Clear a key's window (call on a successful sign-in)."""
    with _lock:
        _hits.pop(key, None)
