"""
Configuration for TD Management and Verification System.
Production-grade settings; DEBUG disabled in production.
"""
import os
from datetime import timedelta

# Base
SECRET_KEY = os.environ.get("SECRET_KEY") or "change-me-in-production-use-long-random-string"
DEBUG = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
TESTING = False

# Database (PostgreSQL in production; SQLite for local setup when PostgreSQL not running)
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if DATABASE_URL:
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}
else:
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _sqlite_path = os.path.join(_project_root, "td_checklist.db").replace("\\", "/")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{_sqlite_path}"
    SQLALCHEMY_ENGINE_OPTIONS = {}
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Redis
REDIS_URL = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"
REDIS_SESSION_PREFIX = "td_session:"
REDIS_RATE_LIMIT_PREFIX = "td_ratelimit:"
REDIS_ACTIVE_SESSIONS_KEY = "td_active_sessions"
REDIS_MAINTENANCE_KEY = "td_maintenance_mode"

# Session (stored in Redis)
SESSION_TYPE = "redis"
SESSION_REDIS = None  # Set in init from REDIS_URL
SESSION_KEY_PREFIX = "td_session:"
PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
SESSION_USE_SIGNER = True
SESSION_COOKIE_NAME = "td_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_PERMANENT = True

# CSRF
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = None
WTF_CSRF_SSL_STRICT = True

# Security
BCRYPT_LOG_ROUNDS = 12
MAX_LOGIN_ATTEMPTS = 5
LOGIN_COOLDOWN_SECONDS = 120
PASSWORD_MIN_LENGTH = 10
PASSWORD_REQUIRE_NUMBER = True
PASSWORD_REQUIRE_LETTER = True
PASSWORD_REQUIRE_SYMBOL = True

# Developer account limit
MAX_DEVELOPER_ACCOUNTS = 2

# Backup
BACKUP_DIR = os.environ.get("BACKUP_DIR") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups")
BACKUP_RETENTION_DAYS = 30

# Pagination
ITEMS_PER_PAGE = 20
TD_ITEMS_PER_PAGE = 50

# Proxy / HTTPS (for Railway)
PREFERRED_URL_SCHEME = "https"
TRUST_PROXY = 1
