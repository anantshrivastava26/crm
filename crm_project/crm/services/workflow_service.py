"""
crm/services/workflow_service.py
Rule-based workflow automation engine.
Jira refs: CRMS-58 (rule engine), CRMS-59 (trigger-based automation),
           CRMS-60 (workflow config UI), CRMS-61 (leads auto-assign),
           CRMS-62 (automated follow-up reminders), CRMS-63 (workflow rules)
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Callable, Optional
from sqlalchemy.orm import Session
from crm.models.customer import Customer
from crm.services.audit_service import AuditService


# ------------------------------------------------------------------ #
# Rule / Trigger model  (CRMS-58, CRMS-59)
# ------------------------------------------------------------------ #
@dataclass
class WorkflowRule:
    """A single rule: when <trigger> and <conditions> → run <actions>."""
    id: str
    name: str
    trigger: str                        # e.g. "customer.created", "stage.changed"
    conditions: list[dict] = field(default_factory=list)   # [{"field": "segment", "op": "eq", "value": "VIP"}]
    actions: list[dict] = field(default_factory=list)      # [{"type": "assign", "to_user_id": 3}]
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "trigger": self.trigger,
            "conditions": self.conditions,
            "actions": self.actions,
            "enabled": self.enabled,
        }


class WorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        # In-memory rule store — replace with DB table for production
        self._rules: dict[str, WorkflowRule] = {}
        self._seed_default_rules()

    # ------------------------------------------------------------------ #
    # Rule management  (CRMS-60)
    # ------------------------------------------------------------------ #
    def add_rule(self, rule: WorkflowRule) -> WorkflowRule:
        self._rules[rule.id] = rule
        return rule

    def remove_rule(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)

    def list_rules(self) -> list[WorkflowRule]:
        return list(self._rules.values())

    def get_rule(self, rule_id: str) -> Optional[WorkflowRule]:
        return self._rules.get(rule_id)

    # ------------------------------------------------------------------ #
    # Trigger dispatcher  (CRMS-59)
    # ------------------------------------------------------------------ #
    def fire(self, trigger: str, customer: Customer, context: Optional[dict] = None) -> list[str]:
        """Fire all rules that match the trigger. Returns list of executed action names."""
        executed = []
        for rule in self._rules.values():
            if not rule.enabled or rule.trigger != trigger:
                continue
            if self._evaluate_conditions(rule.conditions, customer, context or {}):
                executed += self._execute_actions(rule, customer)
        return executed

    # ------------------------------------------------------------------ #
    # Condition evaluator  (CRMS-58)
    # ------------------------------------------------------------------ #
    def _evaluate_conditions(
        self, conditions: list[dict], customer: Customer, ctx: dict
    ) -> bool:
        for cond in conditions:
            field_val = getattr(customer, cond["field"], ctx.get(cond["field"]))
            op = cond.get("op", "eq")
            expected = cond["value"]
            if op == "eq" and field_val != expected:
                return False
            elif op == "neq" and field_val == expected:
                return False
            elif op == "contains" and (expected not in (field_val or "")):
                return False
        return True

    # ------------------------------------------------------------------ #
    # Action executor  (CRMS-61, CRMS-62)
    # ------------------------------------------------------------------ #
    def _execute_actions(self, rule: WorkflowRule, customer: Customer) -> list[str]:
        executed = []
        for action in rule.actions:
            atype = action.get("type")

            if atype == "assign":                       # CRMS-61
                customer.assigned_to = action.get("to_user_id")
                self.db.commit()
                executed.append(f"assigned customer {customer.id} to user {action.get('to_user_id')}")

            elif atype == "set_stage":
                customer.pipeline_stage = action.get("stage")
                self.db.commit()
                executed.append(f"stage → {action.get('stage')}")

            elif atype == "add_tag":
                tags = list(customer.tags or [])
                if action.get("tag") not in tags:
                    tags.append(action["tag"])
                    customer.tags = tags
                    self.db.commit()
                executed.append(f"tag added: {action.get('tag')}")

            elif atype == "reminder":                   # CRMS-62
                # In production: send email / push notification
                executed.append(f"reminder queued: {action.get('message')}")

            self.audit.log(
                user_id=0,
                action="WORKFLOW_ACTION",
                entity="Customer",
                entity_id=customer.id,
                detail={"rule": rule.id, "action": action},
            )
        return executed

    # ------------------------------------------------------------------ #
    # Default rules  (CRMS-63)
    # ------------------------------------------------------------------ #
    def _seed_default_rules(self) -> None:
        self.add_rule(WorkflowRule(
            id="auto_assign_vip",
            name="Auto-assign VIP leads to manager (user 1)",
            trigger="customer.created",
            conditions=[{"field": "segment", "op": "eq", "value": "VIP"}],
            actions=[{"type": "assign", "to_user_id": 1}],
        ))
        self.add_rule(WorkflowRule(
            id="follow_up_reminder",
            name="Send follow-up reminder when stage → Contacted",
            trigger="stage.changed",
            conditions=[{"field": "pipeline_stage", "op": "eq", "value": "Contacted"}],
            actions=[{"type": "reminder", "message": "Follow up with customer within 2 business days."}],
        ))
