"""Shared Flask extension instances.

Moved out of the former single-file app.py so both the app factory and the
public blueprint can import the same objects without a circular import.
"""

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "admin_login"
login_manager.login_message = "Войдите в админ-панель, чтобы продолжить."
login_manager.login_message_category = "warning"
