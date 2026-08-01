"""SQLAlchemy models and the Flask-Login user wrapper.

Moved unchanged from the former single-file app.py — no schema change.
"""

from datetime import datetime

from flask_login import UserMixin

from .extensions import db


class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(32), nullable=True)
    subject = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AdminUser(UserMixin):
    def __init__(self, username: str):
        self.id = username
