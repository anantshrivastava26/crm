"""
crm/services/audit_service.py
Writes and queries the audit log.
Jira refs: CRMS-52 (audit logs), CRMS-55 (audit log table & viewer)
"""

import json
from typing import Optional
from sqlalchemy.orm import Session
from crm.models.audit_log import AuditLog


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        user_id: int,
        action: str,
        entity: Optional[str] = None,
        entity_id: Optional[int] = None,
        detail: Optional[dict] = None,
        ip: Optional[str] = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            detail=json.dumps(detail) if detail else None,
            ip_address=ip,
        )
        self.db.add(entry)
        self.db.commit()
        return entry

    def get_logs(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """CRMS-55: Audit log viewer."""
        q = self.db.query(AuditLog)
        if user_id:
            q = q.filter_by(user_id=user_id)
        if action:
            q = q.filter_by(action=action)
        return q.order_by(AuditLog.timestamp.desc()).limit(limit).all()
