"""
crm/services/segmentation_service.py
Customer segmentation, tagging, and segment-based filters.
Jira refs: CRMS-64 (segment customers), CRMS-65 (tags for prioritisation),
           CRMS-66 (filters based on segments), CRMS-67 (tag management),
           CRMS-68 (segment rules engine), CRMS-69 (segment-based filters)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.orm import Session
from crm.models.customer import Customer
from crm.services.audit_service import AuditService


# ------------------------------------------------------------------ #
# Segment rule model  (CRMS-68)
# ------------------------------------------------------------------ #
@dataclass
class SegmentRule:
    """
    A segment rule automatically classifies customers.
    E.g. company contains 'Enterprise' → segment = 'Enterprise'
    """
    segment_name: str
    conditions: list[dict]          # [{"field": "company", "op": "contains", "value": "LLC"}]
    priority: int = 0               # higher wins on conflict


class SegmentationService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self._segment_rules: list[SegmentRule] = []
        self._seed_default_segments()

    # ------------------------------------------------------------------ #
    # Segment management  (CRMS-64)
    # ------------------------------------------------------------------ #
    def add_segment_rule(self, rule: SegmentRule) -> None:
        self._segment_rules.append(rule)
        self._segment_rules.sort(key=lambda r: -r.priority)

    def classify_customer(self, customer: Customer) -> Optional[str]:
        """CRMS-68: Apply rules engine to determine segment."""
        for rule in self._segment_rules:
            if self._match(rule.conditions, customer):
                return rule.segment_name
        return None

    def auto_segment_all(self) -> dict[str, int]:
        """CRMS-64: Bulk classify all customers."""
        counts: dict[str, int] = {}
        for customer in self.db.query(Customer).all():
            seg = self.classify_customer(customer)
            if seg and customer.segment != seg:
                customer.segment = seg
                counts[seg] = counts.get(seg, 0) + 1
        self.db.commit()
        return counts

    # ------------------------------------------------------------------ #
    # Tag management  (CRMS-65, CRMS-67)
    # ------------------------------------------------------------------ #
    def add_tag(self, customer_id: int, tag: str, actor_id: int = 0) -> Customer:
        customer = self._get_or_raise(customer_id)
        tags = list(customer.tags or [])
        if tag not in tags:
            tags.append(tag.strip().lower())
            customer.tags = tags
            self.db.commit()
            self.audit.log(actor_id, "ADD_TAG", "Customer", customer_id, {"tag": tag})
        return customer

    def remove_tag(self, customer_id: int, tag: str, actor_id: int = 0) -> Customer:
        customer = self._get_or_raise(customer_id)
        tags = [t for t in (customer.tags or []) if t != tag]
        customer.tags = tags
        self.db.commit()
        self.audit.log(actor_id, "REMOVE_TAG", "Customer", customer_id, {"tag": tag})
        return customer

    def list_all_tags(self) -> list[str]:
        """CRMS-67: Return all unique tags across customers."""
        all_tags: set[str] = set()
        for c in self.db.query(Customer).all():
            all_tags.update(c.tags or [])
        return sorted(all_tags)

    # ------------------------------------------------------------------ #
    # Segment-based filters  (CRMS-66, CRMS-69)
    # ------------------------------------------------------------------ #
    def filter_by_segment(self, segment: str) -> list[Customer]:
        """CRMS-69: Filter customers by segment."""
        return self.db.query(Customer).filter_by(segment=segment).all()

    def filter_by_tag(self, tag: str) -> list[Customer]:
        """CRMS-66: Filter customers by tag (JSON contains)."""
        return [c for c in self.db.query(Customer).all() if tag in (c.tags or [])]

    def filter_by_stage(self, stage: str) -> list[Customer]:
        return self.db.query(Customer).filter_by(pipeline_stage=stage).all()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_or_raise(self, customer_id: int) -> Customer:
        c = self.db.query(Customer).filter_by(id=customer_id).first()
        if not c:
            raise ValueError(f"Customer {customer_id} not found.")
        return c

    def _match(self, conditions: list[dict], customer: Customer) -> bool:
        for cond in conditions:
            val = str(getattr(customer, cond["field"], "") or "").lower()
            expected = str(cond["value"]).lower()
            op = cond.get("op", "eq")
            if op == "eq" and val != expected:
                return False
            if op == "contains" and expected not in val:
                return False
            if op == "startswith" and not val.startswith(expected):
                return False
        return True

    def _seed_default_segments(self) -> None:
        self.add_segment_rule(SegmentRule(
            segment_name="Enterprise",
            conditions=[{"field": "company", "op": "contains", "value": "inc"}],
            priority=10,
        ))
        self.add_segment_rule(SegmentRule(
            segment_name="SMB",
            conditions=[{"field": "company", "op": "contains", "value": "llc"}],
            priority=5,
        ))
