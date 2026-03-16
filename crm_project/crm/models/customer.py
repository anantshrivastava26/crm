"""
crm/models/customer.py
Customer and Lead ORM models.
Jira refs: CRMS-44 (import), CRMS-64 (segmentation), CRMS-65 (tagging)
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from crm.models.base import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    phone = Column(String(50))
    company = Column(String(200))
    pipeline_stage = Column(String(100), default="Lead")
    segment = Column(String(100))          # CRMS-64: segmentation
    tags = Column(JSON, default=list)       # CRMS-65: tagging
    custom_fields = Column(JSON, default=dict)  # CRMS-81: custom fields
    assigned_to = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text)

    assignee = relationship("User", back_populates="customers")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "pipeline_stage": self.pipeline_stage,
            "segment": self.segment,
            "tags": self.tags or [],
            "custom_fields": self.custom_fields or {},
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "notes": self.notes,
        }

    def __repr__(self) -> str:
        return f"<Customer {self.name} ({self.email})>"
