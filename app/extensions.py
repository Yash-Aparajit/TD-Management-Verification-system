"""
Flask extensions. Initialized in app factory.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from flask_session import Session
import redis
import os

db = SQLAlchemy()
csrf = CSRFProtect()
login_manager = LoginManager()
session_store = Session()
redis_client = None


def get_redis():
    """Return Redis client (set by app factory)."""
    return redis_client


def init_redis(app):
    """Create Redis connection from app config. Returns None if Redis unavailable (for local dev)."""
    global redis_client
    try:
        redis_client = redis.from_url(
            app.config["REDIS_URL"],
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Test connection
        redis_client.ping()
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, Exception):
        redis_client = None
        # Fall back to filesystem sessions if Redis unavailable
        if app.config.get("SESSION_TYPE") == "redis":
            app.config["SESSION_TYPE"] = "filesystem"
            app.config["SESSION_FILE_DIR"] = app.config.get("SESSION_FILE_DIR") or os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "flask_session"
            )
    return redis_client
