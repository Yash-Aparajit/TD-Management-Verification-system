"""
Operator: read TD, submit checklist. Verification only.
"""
from flask import Blueprint, render_template, redirect, url_for
from ..decorators import operator_or_above
from ..models import Line, FGCode

operator_bp = Blueprint("operator", __name__)


@operator_bp.route("/")
@operator_or_above
def dashboard():
    lines = Line.query.filter_by(is_active=True).order_by(Line.code).all()
    return render_template("operator/dashboard.html", lines=lines)
