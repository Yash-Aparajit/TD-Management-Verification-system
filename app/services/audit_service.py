"""
Audit logging. Never remove audit history when user is deactivated.
"""
from flask import request
from ..extensions import db
from ..models import AuditLog


def log(user_id, username, action, resource=None, resource_id=None, details=None):
    ip = request.remote_addr if request else None
    ua = request.user_agent.string[:255] if request and request.user_agent else None
    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        resource=resource,
        resource_id=str(resource_id) if resource_id is not None else None,
        details=details,
        ip_address=ip,
        user_agent=ua,
    )
    db.session.add(entry)
    db.session.commit()


def log_login_success(user_id, username):
    log(user_id, username, "login_success", resource="auth")


def log_login_failure(username, reason="invalid_credentials"):
    log(None, username, "login_failure", details=reason)


def log_logout(user_id, username):
    log(user_id, username, "logout", resource="auth")


def log_password_change(user_id, username, target_username=None):
    details = f"password changed for {target_username}" if target_username and target_username != username else "own password"
    log(user_id, username, "password_change", resource="user", details=details)


def log_user_created(by_user_id, by_username, new_username, role):
    log(by_user_id, by_username, "user_created", resource="user", resource_id=new_username, details=f"role={role}")


def log_user_deactivated(by_user_id, by_username, target_username):
    log(by_user_id, by_username, "user_deactivated", resource="user", resource_id=target_username)


def log_user_activated(by_user_id, by_username, target_username):
    log(by_user_id, by_username, "user_activated", resource="user", resource_id=target_username)


def log_force_password_reset(by_user_id, by_username, target_username):
    log(by_user_id, by_username, "force_password_reset", resource="user", resource_id=target_username)


def log_maintenance_toggle(by_user_id, by_username, enabled):
    log(by_user_id, by_username, "maintenance_toggle", details=f"enabled={enabled}")


def log_logout_all(by_user_id, by_username):
    log(by_user_id, by_username, "logout_all_sessions")


def log_restore_db(by_user_id, by_username, backup_file):
    log(by_user_id, by_username, "restore_db", details=backup_file)


def log_td_create(by_user_id, by_username, resource, resource_id, details=None):
    log(by_user_id, by_username, "td_create", resource=resource, resource_id=resource_id, details=details)


def log_td_update(by_user_id, by_username, resource, resource_id, details=None):
    log(by_user_id, by_username, "td_update", resource=resource, resource_id=resource_id, details=details)


def log_td_deactivate(by_user_id, by_username, resource, resource_id):
    log(by_user_id, by_username, "td_deactivate", resource=resource, resource_id=resource_id)


def log_verification_submit(user_id, username, verification_id, fg_code):
    log(user_id, username, "verification_submit", resource="verification", resource_id=str(verification_id), details=fg_code)
