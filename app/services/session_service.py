"""
Redis-backed session: touch on each request (inactivity timeout), flush all (logout all), active session tracking.
"""
from flask import session
from ..extensions import get_redis
from ..config import REDIS_SESSION_PREFIX, REDIS_ACTIVE_SESSIONS_KEY, PERMANENT_SESSION_LIFETIME
import time


def _session_key(sid):
    return f"{REDIS_SESSION_PREFIX}{sid}"


def touch_session(user_id):
    """Refresh session activity so Redis TTL is extended when session is saved at end of request."""
    session["last_activity"] = time.time()
    session.modified = True
    r = get_redis()
    if r:
        try:
            sid = session.get("_sid")
            if sid:
                r.sadd(REDIS_ACTIVE_SESSIONS_KEY, f"{user_id}:{sid}")
            r.expire(REDIS_ACTIVE_SESSIONS_KEY, 86400)
        except Exception:
            pass  # Redis unavailable, continue without tracking


def get_active_sessions_count():
    """Count of distinct session IDs in active set (approximate)."""
    r = get_redis()
    if not r:
        return 0
    try:
        return r.scard(REDIS_ACTIVE_SESSIONS_KEY)
    except Exception:
        return 0


def is_session_expired():
    """True if last_activity is older than PERMANENT_SESSION_LIFETIME."""
    last = session.get("last_activity")
    if last is None:
        return False
    return (time.time() - last) > PERMANENT_SESSION_LIFETIME.total_seconds()


def flush_all_sessions():
    """Logout all users: delete all session keys and active set."""
    r = get_redis()
    if not r:
        return
    try:
        prefix = REDIS_SESSION_PREFIX
        keys = list(r.scan_iter(match=f"{prefix}*", count=1000))
        if keys:
            r.delete(*keys)
        r.delete(REDIS_ACTIVE_SESSIONS_KEY)
    except Exception:
        pass  # Redis unavailable
