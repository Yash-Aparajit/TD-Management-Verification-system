"""
TD Management and Verification System - Flask application factory.
Redis-backed sessions, CSRF, role-based access.
"""
import os
from flask import Flask
from flask import g
from . import config
from .extensions import (
    db,
    csrf,
    login_manager,
    session_store,
    init_redis,
    get_redis,
)


def create_app(config_overrides=None):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    env = os.environ.get("FLASK_ENV", "production")
    if env == "development":
        app.config.from_object("app.config")
        app.config["SESSION_COOKIE_SECURE"] = False
        app.config["WTF_CSRF_SSL_STRICT"] = False
    else:
        app.config.from_object("app.config")
    if config_overrides:
        app.config.update(config_overrides)

    # Redis and session (fallback to filesystem if Redis unavailable)
    init_redis(app)
    redis_client = get_redis()
    if redis_client:
        app.config["SESSION_REDIS"] = redis_client
    else:
        # Already set to filesystem in init_redis if Redis unavailable
        pass

    db.init_app(app)
    csrf.init_app(app)
    session_store.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id)) if user_id else None

    # Request hooks: inactivity timeout, refresh session activity, maintenance check
    @app.before_request
    def before_request():
        from flask_login import current_user
        from .services.maintenance_service import is_maintenance_mode
        from .services.session_service import touch_session, is_session_expired
        if current_user.is_authenticated:
            if is_session_expired():
                from flask import redirect, url_for
                from flask_login import logout_user
                logout_user()
                return redirect(url_for("auth.login") + "?expired=1")
            touch_session(current_user.id)
        if is_maintenance_mode():
            from flask import request
            allowed = request.endpoint and (
                request.endpoint.startswith("developer.") or request.endpoint == "auth.logout" or request.endpoint == "maintenance_message"
            )
            if not allowed and request.endpoint != "static":
                from flask import redirect, url_for
                return redirect(url_for("maintenance_message"))

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.admin import admin_bp
    from .routes.developer import developer_bp
    from .routes.operator import operator_bp
    from .routes.verification import verification_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(developer_bp, url_prefix="/developer")
    app.register_blueprint(operator_bp, url_prefix="/operator")
    app.register_blueprint(verification_bp, url_prefix="/verify")

    # Error handlers
    from .routes.errors import register_error_handlers
    register_error_handlers(app)

    @app.route("/maintenance")
    def maintenance_message():
        from flask import render_template
        return render_template("maintenance.html")

    # CLI: daily backup (run via cron/scheduler)
    @app.cli.command("backup-create")
    def backup_create_cmd():
        from .services.backup_service import run_backup, prune_old_backups
        path = run_backup()
        prune_old_backups()
        if path:
            print("Backup created:", path)
        else:
            print("Backup failed.")
            raise SystemExit(1)

    # Root redirect
    @app.route("/")
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role == "developer":
            return redirect(url_for("developer.dashboard"))
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("operator.dashboard"))

    return app
