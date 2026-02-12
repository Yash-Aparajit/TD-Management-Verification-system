"""
Custom error pages. No stack traces in production.
"""
from flask import render_template, redirect, url_for


def register_error_handlers(app):
    @app.errorhandler(401)
    def unauthorized(e):
        return redirect(url_for("auth.login"))

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        if not app.debug:
            return render_template("errors/500.html"), 500
        raise
