"""
Shared SlowAPI rate limiter.

Lives in its own module so endpoint files can import the limiter
without importing app.main (which would create a circular import).

The key function prefers the first hop in X-Forwarded-For — the app
runs behind nginx, so request.client.host would otherwise be the
proxy's address and every user would share one rate-limit bucket.
"""
from fastapi import Request
from slowapi import Limiter


def client_ip(request: Request) -> str:
    """Best-effort per-client key: X-Forwarded-For first, else peer IP."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip)
