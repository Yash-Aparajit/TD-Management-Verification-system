"""
Developer-only: users, backup, restore, maintenance, system dashboard, logout all.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import current_user
from ..extensions import db
from ..models import User, AuditLog
from ..decorators import developer_required
from ..services.audit_service import (
    log_user_created,
    log_user_deactivated,
    log_user_activated,
    log_force_password_reset,
    log_maintenance_toggle,
    log_logout_all,
    log_restore_db,
)
from ..services.backup_service import run_backup, list_backups, restore_from_file, prune_old_backups
from ..services.maintenance_service import is_maintenance_mode, set_maintenance_mode
from ..services.session_service import flush_all_sessions, get_active_sessions_count
from ..utils.validators import validate_password
from ..config import MAX_DEVELOPER_ACCOUNTS
import os
import time

developer_bp = Blueprint("developer", __name__)


@developer_bp.route("/")
@developer_required
def dashboard():
    from ..extensions import get_redis
    from ..models import User, Line, FGCode, TDItem, Verification
    r = get_redis()
    db_ok = True
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        db_ok = False
    redis_ok = False
    redis_available = r is not None
    if r:
        try:
            redis_ok = r.ping()
        except Exception:
            redis_ok = False
    active_sessions = get_active_sessions_count()
    maintenance = is_maintenance_mode()
    backups = list_backups()[:10]
    # Statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_lines = Line.query.count()
    active_lines = Line.query.filter_by(is_active=True).count()
    total_fg_codes = FGCode.query.count()
    active_fg_codes = FGCode.query.filter_by(is_active=True).count()
    total_td_items = TDItem.query.count()
    total_verifications = Verification.query.count()
    return render_template(
        "developer/dashboard.html",
        db_ok=db_ok,
        redis_ok=redis_ok,
        redis_available=redis_available,
        active_sessions=active_sessions,
        maintenance=maintenance,
        backups=backups,
        total_users=total_users,
        active_users=active_users,
        total_lines=total_lines,
        active_lines=active_lines,
        total_fg_codes=total_fg_codes,
        active_fg_codes=active_fg_codes,
        total_td_items=total_td_items,
        total_verifications=total_verifications,
    )


@developer_bp.route("/maintenance", methods=["GET", "POST"])
@developer_required
def maintenance_page():
    if request.method == "GET":
        return render_template("developer/maintenance.html", enabled=is_maintenance_mode())
    enabled = request.form.get("enable") == "1"
    set_maintenance_mode(enabled)
    log_maintenance_toggle(current_user.id, current_user.username, enabled)
    flash("Maintenance mode " + ("enabled" if enabled else "disabled") + ".", "success")
    return redirect(url_for("developer.dashboard"))


# ---- Users ----
@developer_bp.route("/users")
@developer_required
def users_list():
    users = User.query.order_by(User.username).all()
    return render_template("developer/users_list.html", users=users)


@developer_bp.route("/users/create", methods=["GET", "POST"])
@developer_required
def user_create():
    if request.method == "GET":
        return render_template("developer/user_form.html", user=None)
    username = (request.form.get("username") or "").strip()
    full_name = (request.form.get("full_name") or "").strip()
    role = (request.form.get("role") or "operator").strip()
    password = request.form.get("password") or ""
    if role not in ("developer", "admin", "operator"):
        role = "operator"
    if role == "developer":
        dev_count = User.query.filter_by(role="developer", is_active=True).count()
        if dev_count >= MAX_DEVELOPER_ACCOUNTS:
            flash(f"Maximum {MAX_DEVELOPER_ACCOUNTS} developer accounts allowed.", "danger")
            return render_template("developer/user_form.html", user=None)
    if not username:
        flash("Username is required.", "danger")
        return render_template("developer/user_form.html", user=None)
    if User.query.filter_by(username=username).first():
        flash("Username already exists.", "danger")
        return render_template("developer/user_form.html", user=None)
    ok, err = validate_password(password)
    if not ok:
        flash(err, "danger")
        return render_template("developer/user_form.html", user=None)
    user = User(
        username=username,
        full_name=full_name or username,
        role=role,
        is_active=True,
        must_change_password=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    log_user_created(current_user.id, current_user.username, username, role)
    flash("User created. They must change password on first login.", "success")
    return redirect(url_for("developer.users_list"))


@developer_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@developer_required
def user_deactivate(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate yourself.", "danger")
        return redirect(url_for("developer.users_list"))
    if user.role == "developer":
        dev_count = User.query.filter_by(role="developer", is_active=True).count()
        if dev_count <= 1:
            flash("Cannot deactivate the last developer.", "danger")
            return redirect(url_for("developer.users_list"))
    user.is_active = False
    user.updated_by_id = current_user.id
    db.session.commit()
    log_user_deactivated(current_user.id, current_user.username, user.username)
    flash("User deactivated.", "success")
    return redirect(url_for("developer.users_list"))


@developer_bp.route("/users/<int:user_id>/activate", methods=["POST"])
@developer_required
def user_activate(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = True
    user.updated_by_id = current_user.id
    db.session.commit()
    log_user_activated(current_user.id, current_user.username, user.username)
    flash("User activated.", "success")
    return redirect(url_for("developer.users_list"))


@developer_bp.route("/users/<int:user_id>/force-reset-password", methods=["GET", "POST"])
@developer_required
def force_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "GET":
        return render_template("developer/force_reset_password.html", target_user=user)
    new_password = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""
    if new_password != confirm:
        flash("Passwords do not match.", "danger")
        return render_template("developer/force_reset_password.html", target_user=user)
    ok, err = validate_password(new_password)
    if not ok:
        flash(err, "danger")
        return render_template("developer/force_reset_password.html", target_user=user)
    user.set_password(new_password)
    user.must_change_password = True
    db.session.commit()
    log_force_password_reset(current_user.id, current_user.username, user.username)
    flash("Password reset. User must change password on next login.", "success")
    return redirect(url_for("developer.users_list"))


# ---- Backup / Restore ----
@developer_bp.route("/backup")
@developer_required
def backup_list():
    backups = list_backups()
    return render_template("developer/backup_list.html", backups=backups)


@developer_bp.route("/backup/create")
@developer_required
def backup_create():
    path = run_backup()
    if path:
        prune_old_backups()
        flash("Backup created.", "success")
    else:
        flash("Backup failed. Ensure pg_dump is available and DATABASE_URL is set.", "danger")
    return redirect(url_for("developer.backup_list"))


@developer_bp.route("/backup/download/<path:filename>")
@developer_required
def backup_download(filename):
    from ..config import BACKUP_DIR
    import urllib.parse
    base = os.path.basename(filename)
    if not base.startswith("td_backup_") or not base.endswith(".sql"):
        flash("Invalid file.", "danger")
        return redirect(url_for("developer.backup_list"))
    path = os.path.join(BACKUP_DIR, base)
    if not os.path.isfile(path):
        flash("File not found.", "danger")
        return redirect(url_for("developer.backup_list"))
    return send_file(path, as_attachment=True, download_name=base)


@developer_bp.route("/backup/restore", methods=["GET", "POST"])
@developer_required
def backup_restore():
    if request.method == "GET":
        backups = list_backups()
        return render_template("developer/restore_confirm.html", backups=backups)
    backup_path = request.form.get("backup_path")
    confirm = request.form.get("confirm") or ""
    confirm2 = request.form.get("confirm2") or ""
    if confirm != "RESTORE" or confirm2 != "RESTORE":
        flash("You must type RESTORE in both boxes to confirm.", "danger")
        return redirect(url_for("developer.backup_restore"))
    if not backup_path or not os.path.isfile(backup_path):
        flash("Invalid backup file.", "danger")
        return redirect(url_for("developer.backup_list"))
    log_restore_db(current_user.id, current_user.username, backup_path)
    success, err = restore_from_file(backup_path, current_user.id, current_user.username)
    if success:
        flash("Database restored. All users were logged out.", "success")
    else:
        flash("Restore failed: " + (err or "unknown"), "danger")
    return redirect(url_for("developer.backup_list"))


@developer_bp.route("/logout-all", methods=["POST"])
@developer_required
def logout_all():
    flush_all_sessions()
    log_logout_all(current_user.id, current_user.username)
    flash("All sessions have been logged out.", "success")
    return redirect(url_for("developer.dashboard"))


# ---- Audit logs (developer view) ----
@developer_bp.route("/audit-logs")
@developer_required
def audit_logs():
    page = request.args.get("page", 1, type=int)
    from ..config import ITEMS_PER_PAGE
    q = AuditLog.query.order_by(AuditLog.created_at.desc())
    pagination = q.paginate(page=page, per_page=ITEMS_PER_PAGE)
    return render_template("developer/audit_logs.html", pagination=pagination)


# ---- Active sessions ----
@developer_bp.route("/sessions")
@developer_required
def active_sessions():
    return render_template("developer/active_sessions.html", count=get_active_sessions_count())
