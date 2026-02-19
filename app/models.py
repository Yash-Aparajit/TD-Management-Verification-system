"""
SQLAlchemy models for TD Management and Verification System.
Soft delete (is_active) for users, FG codes, TD items. Audit-friendly.
"""
from datetime import datetime
from flask_login import UserMixin
import bcrypt
from .extensions import db
import re


def normalize_fg_code(value):
    """Uppercase FG code."""
    return (value or "").strip().upper()


def normalize_whitespace(value):
    """Trim and collapse whitespace."""
    return (value or "").strip() if value else ""


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # developer, admin, operator
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    must_change_password = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    updated_by = db.relationship("User", remote_side=[id], foreign_keys=[updated_by_id])

    __table_args__ = (db.CheckConstraint("role IN ('developer', 'admin', 'operator')", name="ck_user_role"),)

    def set_password(self, raw_password):
        self.password_hash = bcrypt.hashpw(
            raw_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
        ).decode("utf-8")
        self.updated_at = datetime.utcnow()

    def check_password(self, raw_password):
        try:
            return bcrypt.checkpw(
                raw_password.encode("utf-8"), self.password_hash.encode("utf-8")
            )
        except Exception:
            return False

    def is_developer(self):
        return self.role == "developer"

    def is_admin(self):
        return self.role == "admin"

    def is_operator(self):
        return self.role == "operator"

    def can_manage_td(self):
        return self.role in ("developer", "admin")

    def can_verify(self):
        return self.role in ("developer", "admin", "operator")

    def can_manage_users(self):
        return self.role == "developer"

    def __repr__(self):
        return f"<User {self.username}>"


class Line(db.Model):
    __tablename__ = "lines"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])

    fg_codes = db.relationship("FGCode", back_populates="line", lazy="dynamic")


class FGCode(db.Model):
    __tablename__ = "fg_codes"
    id = db.Column(db.Integer, primary_key=True)
    line_id = db.Column(db.Integer, db.ForeignKey("lines.id"), nullable=False)
    code = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
    line = db.relationship("Line", back_populates="fg_codes")

    td_items = db.relationship("TDItem", back_populates="fg_code", lazy="dynamic")

    __table_args__ = (db.UniqueConstraint("line_id", "code", name="uq_fg_line_code"),)


class TDItem(db.Model):
    """Child Part or Consumable under an FG Code. Master data; not modified by verification."""
    __tablename__ = "td_items"
    id = db.Column(db.Integer, primary_key=True)
    fg_id = db.Column(db.Integer, db.ForeignKey("fg_codes.id"), nullable=False)
    item_code = db.Column(db.String(80), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    item_type = db.Column(db.String(20), nullable=False)  # child_part, consumable
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
    fg_code = db.relationship("FGCode", back_populates="td_items")

    __table_args__ = (
        db.UniqueConstraint("fg_id", "item_code", name="uq_fg_item_code"),
        db.CheckConstraint("item_type IN ('child_part', 'consumable')", name="ck_td_item_type"),
        db.CheckConstraint("quantity >= 0", name="ck_td_quantity_nonneg"),
    )


class Verification(db.Model):
    """One verification submission (checklist). Immutable once saved."""
    __tablename__ = "verifications"
    id = db.Column(db.Integer, primary_key=True)
    fg_id = db.Column(db.Integer, db.ForeignKey("fg_codes.id"), nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    verified_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    fg_code = db.relationship("FGCode", backref=db.backref("verifications", lazy="dynamic"))
    operator = db.relationship("User", foreign_keys=[operator_id])

    items = db.relationship("VerificationItem", back_populates="verification", lazy="joined", cascade="all, delete-orphan")


class VerificationItem(db.Model):
    """Per-item actual quantity recorded in a verification. Immutable."""
    __tablename__ = "verification_items"
    id = db.Column(db.Integer, primary_key=True)
    verification_id = db.Column(db.Integer, db.ForeignKey("verifications.id"), nullable=False)
    td_item_id = db.Column(db.Integer, db.ForeignKey("td_items.id"), nullable=False)
    expected_quantity = db.Column(db.Numeric(12, 2), nullable=False)
    actual_quantity = db.Column(db.Numeric(12, 2), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    verification = db.relationship("Verification", back_populates="items")
    td_item = db.relationship("TDItem", backref=db.backref("verification_items", lazy="dynamic"))


class AuditLog(db.Model):
    """System audit trail. Never remove when user is deactivated."""
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    username = db.Column(db.String(80), nullable=True)  # denormalized for history
    action = db.Column(db.String(80), nullable=False)
    resource = db.Column(db.String(80), nullable=True)
    resource_id = db.Column(db.String(40), nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("audit_logs", lazy="dynamic"))


class LoginAttempt(db.Model):
    """Login attempts for rate limiting and audit."""
    __tablename__ = "login_attempts"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, index=True)
    success = db.Column(db.Boolean, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
