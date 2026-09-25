"""
Small in-memory rate limiter (Phase 2).

Deliberately dependency-free: the project must run locally without Redis or an
extra package. It protects the authentication endpoints against brute force and
OTP spam. For a multi-process deployment a shared store would be required -
documented as a limitation.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Tuple

from fastapi import HTTPException, Request, status

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("rate_limit")

_lock = threading.Lock()
_hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    """
    Resolve the caller IP.

    ``X-Forwarded-For`` is client controlled, so honouring it unconditionally
    would let any caller rotate their identity and bypass every limit. It is
    only read when the operator declares the app runs behind a trusted proxy
    (``TRUST_PROXY_HEADERS=true``).
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def is_rate_limited(scope: str, identity: str, limit: int, window_seconds: int) -> bool:
    """Record a hit and report whether the caller exceeded ``limit``."""
    now = time.time()
    key = (scope, identity)
    with _lock:
        bucket = _hits[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
        return False


def reset_rate_limits() -> None:
    """Testing helper: clear all counters."""
    with _lock:
        _hits.clear()


def rate_limit(scope: str, limit: int, window_seconds: int | None = None) -> Callable[[Request], None]:
    """
    Build a FastAPI dependency that limits ``scope`` per client IP.

    Usage::

        @app.post("/api/auth/login", dependencies=[Depends(rate_limit("login", settings.login_rate_limit))])
    """
    window = window_seconds or settings.rate_limit_window_seconds

    def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        identity = _client_ip(request)
        if is_rate_limited(scope, identity, limit, window):
            logger.warning("Rate limit exceeded: scope=%s ip=%s limit=%s/%ss", scope, identity, limit, window)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests for {scope}. Please wait and try again.",
                headers={"Retry-After": str(window)},
            )

    return dependency
