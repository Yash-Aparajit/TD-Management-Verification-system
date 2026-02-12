"""
Login rate limiting via Redis: max 5 attempts → 2-minute cooldown.
"""
from ..extensions import get_redis
from ..config import REDIS_RATE_LIMIT_PREFIX, MAX_LOGIN_ATTEMPTS, LOGIN_COOLDOWN_SECONDS


def get_rate_limit_key(identifier):
    return f"{REDIS_RATE_LIMIT_PREFIX}{identifier}"


def is_rate_limited(identifier):
    """Check if identifier is currently rate limited"""
    r = get_redis()
    if not r:
        return False

    try:
        key = get_rate_limit_key(identifier)
        val = r.get(key)

        if val is None:
            return False

        # Redis returns bytes → decode safely
        if isinstance(val, bytes):
            val = val.decode("utf-8", errors="ignore")

        return val == "blocked"

    except Exception:
        return False


def get_remaining_cooldown(identifier):
    """Return seconds remaining in cooldown, or 0."""
    r = get_redis()
    if not r:
        return 0
    try:
        key = get_rate_limit_key(identifier)
        ttl = r.ttl(key)
        return max(0, ttl) if ttl > 0 else 0
    except Exception:
        return 0


def record_failed_attempt(identifier):
    """
    Record a failed login. After MAX_LOGIN_ATTEMPTS failures, set cooldown.
    Returns (attempts_so_far, is_now_blocked).
    """
    r = get_redis()
    if not r:
        return 0, False
    try:
        key = get_rate_limit_key(identifier)
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, LOGIN_COOLDOWN_SECONDS)
        results = pipe.execute()
        count = results[0]
        if count >= MAX_LOGIN_ATTEMPTS:
            r.setex(key, LOGIN_COOLDOWN_SECONDS, "blocked")
            return count, True
        return count, False
    except Exception:
        return 0, False  # Redis unavailable, allow login


def clear_rate_limit(identifier):
    """Clear rate limit for identifier (e.g. after successful login)."""
    r = get_redis()
    if r:
        try:
            r.delete(get_rate_limit_key(identifier))
        except Exception:
            pass  # Redis unavailable
