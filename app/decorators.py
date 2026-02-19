"""
Role-based and login decorators. Backend-only enforcement; never rely on frontend.
"""
from functools import wraps
from flask import abort
from flask_login import current_user


def login_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        return f(*args, **kwargs)
    return inner


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return inner
    return decorator


def developer_required(f):
    return role_required("developer")(f)


def admin_required(f):
    """Admin or developer."""
    return role_required("developer", "admin")(f)


def operator_or_above(f):
    """Operator, admin, or developer."""
    return role_required("developer", "admin", "operator")(f)
