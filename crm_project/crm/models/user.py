"""
crm/models/user.py
User model with RBAC support.
Jira refs: CRMS-51 (RBAC), CRMS-52 (audit logs), CRMS-53 (encryption), CRMS-57 (session mgmt)
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text
from sqlalchemy.orm import relationship
import enum
from crm.models.base import Base


class Role(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    SALES_EXEC = "sales_exec"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)  # CRMS-56
    role = Column(Enum(Role), default=Role.SALES_EXEC)   # CRMS-54 RBAC
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    customers = relationship("Customer", back_populates="assignee")
    audit_logs = relationship("AuditLog", back_populates="user")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value if self.role else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.username} [{self.role}]>"
