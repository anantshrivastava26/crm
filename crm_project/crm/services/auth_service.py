"""
crm/services/auth_service.py
Authentication, RBAC, and session management.
Jira refs: CRMS-51 (RBAC), CRMS-53 (encryption), CRMS-54 (RBAC impl),
           CRMS-56 (password hashing), CRMS-57 (session management),
           CRMS-38 (user registration & login)
"""

import bcrypt
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional
from sqlalchemy.orm import Session
from crm.models.user import User, Role
from crm.services.audit_service import AuditService


# In-memory session store (use Redis/DB in production)
_sessions: dict[str, dict] = {}

SESSION_TTL_MINUTES = 30


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    # ------------------------------------------------------------------ #
    # Registration  (CRMS-38)
    # ------------------------------------------------------------------ #
    def register(self, username: str, email: str, password: str, role: Role = Role.SALES_EXEC) -> User:
        if self.db.query(User).filter_by(email=email).first():
            raise ValueError(f"Email '{email}' already registered.")

        password_hash = self._hash_password(password)
        user = User(username=username, email=email, password_hash=password_hash, role=role)
        self.db.add(user)
        self.db.commit()
        self.audit.log(user_id=user.id, action="REGISTER", entity="User", entity_id=user.id)
        return user

    # ------------------------------------------------------------------ #
    # Login  (CRMS-38)
    # ------------------------------------------------------------------ #
    def login(self, email: str, password: str, ip: Optional[str] = None) -> str:
        """Authenticate user, return session token."""
        user = self.db.query(User).filter_by(email=email).first()
        if not user or not self._verify_password(password, user.password_hash):
            raise PermissionError("Invalid credentials.")

        token = secrets.token_hex(32)
        _sessions[token] = {
            "user_id": user.id,
            "role": user.role.value,
            "expires_at": datetime.utcnow() + timedelta(minutes=SESSION_TTL_MINUTES),
        }
        user.last_login = datetime.utcnow()
        self.db.commit()
        self.audit.log(user_id=user.id, action="LOGIN", entity="User", entity_id=user.id, ip=ip)
        return token

    # ------------------------------------------------------------------ #
    # Session  (CRMS-57)
    # ------------------------------------------------------------------ #
    def get_session(self, token: str) -> Optional[dict]:
        session = _sessions.get(token)
        if not session:
            return None
        if datetime.utcnow() > session["expires_at"]:
            del _sessions[token]
            return None
        return session

    def logout(self, token: str) -> None:
        _sessions.pop(token, None)

    # ------------------------------------------------------------------ #
    # RBAC  (CRMS-51, CRMS-54)
    # ------------------------------------------------------------------ #
    ROLE_PERMISSIONS: dict[str, set[str]] = {
        Role.ADMIN.value:      {"read", "write", "delete", "admin", "audit"},
        Role.MANAGER.value:    {"read", "write", "delete", "audit"},
        Role.SALES_EXEC.value: {"read", "write"},
        Role.VIEWER.value:     {"read"},
    }

    def has_permission(self, token: str, permission: str) -> bool:
        session = self.get_session(token)
        if not session:
            return False
        allowed = self.ROLE_PERMISSIONS.get(session["role"], set())
        return permission in allowed

    def require_permission(self, token: str, permission: str) -> None:
        if not self.has_permission(token, permission):
            raise PermissionError(f"Permission '{permission}' required.")

    # ------------------------------------------------------------------ #
    # Helpers  (CRMS-56)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())
