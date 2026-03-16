"""
crm/models/audit_log.py
Audit log model — tracks all user actions.
Jira ref: CRMS-52 (audit logs), CRMS-55 (audit log table & viewer)
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from crm.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100), nullable=False)   # e.g. "CREATE_CUSTOMER"
    entity = Column(String(100))                   # e.g. "Customer"
    entity_id = Column(Integer)
    detail = Column(Text)                          # JSON-serialised change detail
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(50))

    user = relationship("User", back_populates="audit_logs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "entity": self.entity,
            "entity_id": self.entity_id,
            "detail": self.detail,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "ip_address": self.ip_address,
        }

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by user {self.user_id} @ {self.timestamp}>"
