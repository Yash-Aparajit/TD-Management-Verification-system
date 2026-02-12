"""
Maintenance mode. Developer-only. Blocks all non-developer access.
"""
from ..extensions import get_redis
from ..config import REDIS_MAINTENANCE_KEY
import redis


def is_maintenance_mode():
    r = get_redis()
    if not r:
        return False
    try:
        return r.get(REDIS_MAINTENANCE_KEY) == "1"
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, Exception):
        return False


def set_maintenance_mode(enabled):
    r = get_redis()
    if not r:
        return
    try:
        if enabled:
            r.set(REDIS_MAINTENANCE_KEY, "1")
        else:
            r.delete(REDIS_MAINTENANCE_KEY)
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, Exception):
        pass
