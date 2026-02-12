"""
Verification: load TD by Line -> FG, submit checklist. Records immutable once saved.
Does not modify TD master.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from ..extensions import db
from ..models import Line, FGCode, TDItem, Verification, VerificationItem
from ..decorators import operator_or_above
from ..services.audit_service import log_verification_submit

verification_bp = Blueprint("verification", __name__)


@verification_bp.route("/")
@operator_or_above
def index():
    lines = Line.query.filter_by(is_active=True).order_by(Line.code).all()
    return render_template("verification/index.html", lines=lines)


@verification_bp.route("/line/<int:line_id>")
@operator_or_above
def fgs_for_line(line_id):
    line = Line.query.filter_by(id=line_id, is_active=True).first_or_404()
    fgs = FGCode.query.filter_by(line_id=line_id, is_active=True).order_by(FGCode.code).all()
    return render_template("verification/select_fg.html", line=line, fgs=fgs)


@verification_bp.route("/fg/<int:fg_id>")
@operator_or_above
def load_checklist(fg_id):
    fg = FGCode.query.filter_by(id=fg_id, is_active=True).first_or_404()
    items = TDItem.query.filter_by(fg_id=fg_id, is_active=True).order_by(TDItem.item_code).all()
    return render_template("verification/checklist.html", fg=fg, items=items)


@verification_bp.route("/fg/<int:fg_id>/submit", methods=["POST"])
@operator_or_above
def submit_checklist(fg_id):
    fg = FGCode.query.filter_by(id=fg_id, is_active=True).first_or_404()
    items = TDItem.query.filter_by(fg_id=fg_id, is_active=True).order_by(TDItem.item_code).all()
    if not items:
        flash("No TD items to verify for this FG code.", "warning")
        return redirect(url_for("verification.index"))
    notes = (request.form.get("notes") or "").strip()[:2000]
    ver = Verification(fg_id=fg_id, operator_id=current_user.id, notes=notes or None)
    db.session.add(ver)
    db.session.flush()
    for item in items:
        key = f"actual_{item.id}"
        try:
            actual = float(request.form.get(key, 0) or 0)
        except ValueError:
            actual = 0
        vi = VerificationItem(
            verification_id=ver.id,
            td_item_id=item.id,
            expected_quantity=item.quantity,
            actual_quantity=actual,
            unit=item.unit,
        )
        db.session.add(vi)
    db.session.commit()
    log_verification_submit(current_user.id, current_user.username, ver.id, fg.code)
    flash("Verification submitted successfully. It cannot be modified.", "success")
    return redirect(url_for("verification.result", verification_id=ver.id))


@verification_bp.route("/result/<int:verification_id>")
@operator_or_above
def result(verification_id):
    ver = Verification.query.get_or_404(verification_id)
    # Ensure the current user can view this verification (same role rules as submit)
    fg = ver.fg_code
    return render_template("verification/result.html", verification=ver, fg=fg)
