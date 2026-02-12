"""
Authentication: login, logout, change password. Session-based; Redis rate limiting.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from ..extensions import db
from ..models import User, LoginAttempt
from flask_login import login_required
from ..services.rate_limit_service import (
    is_rate_limited,
    get_remaining_cooldown,
    record_failed_attempt,
    clear_rate_limit,
)
from ..services.audit_service import (
    log_login_success,
    log_login_failure,
    log_logout,
    log_password_change,
)
from ..utils.validators import validate_password

auth_bp = Blueprint("auth", __name__)


def _get_client_id():
    return request.remote_addr or "unknown"


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "GET":
        return render_template("auth/login.html", expired=request.args.get("expired"))
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    if not username:
        flash("Username is required.", "danger")
        return render_template("auth/login.html")
    client_id = _get_client_id()
    if is_rate_limited(client_id) or is_rate_limited(username):
        secs = max(get_remaining_cooldown(client_id), get_remaining_cooldown(username))
        flash(f"Too many failed attempts. Try again in {secs} seconds.", "danger")
        return render_template("auth/login.html")
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        record_failed_attempt(client_id)
        record_failed_attempt(username)
        attempt = LoginAttempt(username=username, success=False, ip_address=client_id)
        db.session.add(attempt)
        db.session.commit()
        log_login_failure(username, "invalid_credentials")
        flash("Invalid username or password.", "danger")
        return render_template("auth/login.html")
    if not user.is_active:
        log_login_failure(username, "account_inactive")
        flash("Account is deactivated. Contact an administrator.", "danger")
        return render_template("auth/login.html")
    clear_rate_limit(client_id)
    clear_rate_limit(username)
    attempt = LoginAttempt(username=username, success=True, ip_address=client_id)
    db.session.add(attempt)
    db.session.commit()
    log_login_success(user.id, user.username)
    login_user(user)
    if user.must_change_password:
        return redirect(url_for("auth.change_password", first=1))
    return redirect(url_for("index"))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    if current_user.is_authenticated:
        log_logout(current_user.id, current_user.username)
        logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    first = request.args.get("first") == "1"
    if request.method == "GET":
        return render_template("auth/change_password.html", first=first)
    current = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""
    if not first and not current_user.check_password(current):
        flash("Current password is incorrect.", "danger")
        return render_template("auth/change_password.html", first=first)
    if new_password != confirm:
        flash("New password and confirmation do not match.", "danger")
        return render_template("auth/change_password.html", first=first)
    ok, err = validate_password(new_password)
    if not ok:
        flash(err, "danger")
        return render_template("auth/change_password.html", first=first)
    current_user.set_password(new_password)
    current_user.must_change_password = False
    db.session.commit()
    log_password_change(current_user.id, current_user.username)
    flash("Password updated successfully.", "success")
    if first:
        return redirect(url_for("index"))
    return redirect(url_for("index"))
