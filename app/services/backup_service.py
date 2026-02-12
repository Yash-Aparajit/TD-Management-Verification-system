"""
Database backup and restore. Automatic daily backup; 30-day retention.
Restore: double confirmation, optional password, maintenance mode, flush Redis.
"""
import os
import subprocess
import glob
from datetime import datetime, timedelta
from ..extensions import db
from .maintenance_service import set_maintenance_mode
from .session_service import flush_all_sessions
from ..config import BACKUP_DIR, BACKUP_RETENTION_DAYS


def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def get_db_url():
    from flask import current_app
    return current_app.config["SQLALCHEMY_DATABASE_URI"]


def run_backup():
    """Create a timestamped PostgreSQL dump. Returns path to backup file or None."""
    ensure_backup_dir()
    url = get_db_url()
    if not url or url.startswith("sqlite"):
        return None
    # pg_dump style: extract connection params from URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        user = parsed.username
        password = parsed.password
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        dbname = parsed.path.lstrip("/") or "td_checklist"
        env = os.environ.copy()
        if password:
            env["PGPASSWORD"] = password
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(BACKUP_DIR, f"td_backup_{stamp}.sql")
        cmd = [
            "pg_dump",
            "-h", host,
            "-p", str(port),
            "-U", user or "postgres",
            "-d", dbname,
            "-f", path,
            "--no-owner",
            "--no-acl",
        ]
        subprocess.run(cmd, env=env, check=True, capture_output=True, timeout=300)
        return path
    except Exception:
        return None


def prune_old_backups():
    """Delete backups older than BACKUP_RETENTION_DAYS."""
    ensure_backup_dir()
    pattern = os.path.join(BACKUP_DIR, "td_backup_*.sql")
    cutoff = datetime.utcnow() - timedelta(days=BACKUP_RETENTION_DAYS)
    for path in glob.glob(pattern):
        try:
            if os.path.getmtime(path) < cutoff.timestamp():
                os.remove(path)
        except OSError:
            pass


def list_backups():
    """Return list of (filename, full_path, mtime) sorted by mtime desc."""
    ensure_backup_dir()
    pattern = os.path.join(BACKUP_DIR, "td_backup_*.sql")
    files = []
    for path in glob.glob(pattern):
        try:
            mtime = os.path.getmtime(path)
            files.append((os.path.basename(path), path, datetime.fromtimestamp(mtime)))
        except OSError:
            pass
    files.sort(key=lambda x: x[2], reverse=True)
    return files


def restore_from_file(backup_path, current_user_id, current_username):
    """
    Restore DB from backup. Caller must have confirmed.
    Enables maintenance, flushes Redis, restores, then caller can disable maintenance.
    """
    if not os.path.isfile(backup_path):
        return False, "Backup file not found"
    set_maintenance_mode(True)
    flush_all_sessions()
    url = get_db_url()
    if not url or url.startswith("sqlite"):
        set_maintenance_mode(False)
        return False, "PostgreSQL required for restore"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        user = parsed.username
        password = parsed.password
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        dbname = parsed.path.lstrip("/") or "td_checklist"
        env = os.environ.copy()
        if password:
            env["PGPASSWORD"] = password
        cmd = [
            "psql",
            "-h", host,
            "-p", str(port),
            "-U", user or "postgres",
            "-d", dbname,
            "-f", backup_path,
        ]
        subprocess.run(cmd, env=env, check=True, capture_output=True, timeout=600)
        return True, None
    except subprocess.CalledProcessError as e:
        set_maintenance_mode(False)
        return False, str(e.stderr or e) if isinstance(e.stderr, str) else "Restore failed"
    except Exception as e:
        set_maintenance_mode(False)
        return False, str(e)
