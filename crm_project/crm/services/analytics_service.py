"""
crm/services/analytics_service.py
KPI calculations and dashboard data aggregation.
Jira refs: CRMS-75 (analytics, dashboards & KPIs), CRMS-78 (dashboard UI data),
           CRMS-79 (KPI calculations), CRMS-80 (chart integration)
"""

from __future__ import annotations
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional
from sqlalchemy.orm import Session
from crm.models.customer import Customer


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Dashboard summary  (CRMS-78)
    # ------------------------------------------------------------------ #
    def dashboard_summary(self) -> dict:
        """Top-level KPI card data for the dashboard."""
        customers = self.db.query(Customer).all()
        total = len(customers)
        by_stage = defaultdict(int)
        by_segment = defaultdict(int)
        for c in customers:
            by_stage[c.pipeline_stage or "Unknown"] += 1
            by_segment[c.segment or "Unclassified"] += 1

        return {
            "total_customers": total,
            "by_stage": dict(by_stage),
            "by_segment": dict(by_segment),
            "conversion_rate": self._conversion_rate(customers),
            "new_this_month": self._new_this_period(customers, days=30),
            "new_this_week": self._new_this_period(customers, days=7),
        }

    # ------------------------------------------------------------------ #
    # KPI calculations  (CRMS-79)
    # ------------------------------------------------------------------ #
    def conversion_rate(self) -> float:
        customers = self.db.query(Customer).all()
        return self._conversion_rate(customers)

    def avg_time_to_close(self) -> Optional[float]:
        """Average days from creation to 'Closed Won'."""
        closed = self.db.query(Customer).filter_by(pipeline_stage="Closed Won").all()
        if not closed:
            return None
        deltas = [
            (datetime.utcnow() - c.created_at).days
            for c in closed
            if c.created_at
        ]
        return round(sum(deltas) / len(deltas), 1) if deltas else None

    def pipeline_velocity(self) -> dict[str, int]:
        """Count of customers per pipeline stage — for funnel chart (CRMS-80)."""
        rows = self.db.query(Customer).all()
        velocity: dict[str, int] = defaultdict(int)
        for c in rows:
            velocity[c.pipeline_stage or "Unknown"] += 1
        return dict(velocity)

    def leads_over_time(self, days: int = 30) -> list[dict]:
        """
        Daily new-customer counts for line chart (CRMS-80).
        Returns list of {"date": "YYYY-MM-DD", "count": N}
        """
        since = datetime.utcnow() - timedelta(days=days)
        rows = (
            self.db.query(Customer)
            .filter(Customer.created_at >= since)
            .all()
        )
        daily: dict[str, int] = defaultdict(int)
        for c in rows:
            if c.created_at:
                day = c.created_at.strftime("%Y-%m-%d")
                daily[day] += 1

        # Fill gaps
        result = []
        for i in range(days):
            day = (since + timedelta(days=i)).strftime("%Y-%m-%d")
            result.append({"date": day, "count": daily.get(day, 0)})
        return result

    def top_assignees(self, limit: int = 5) -> list[dict]:
        """Leaderboard of assignees by number of customers (CRMS-79)."""
        rows = self.db.query(Customer).all()
        counts: dict[int, int] = defaultdict(int)
        for c in rows:
            if c.assigned_to:
                counts[c.assigned_to] += 1
        sorted_items = sorted(counts.items(), key=lambda x: -x[1])[:limit]
        return [{"user_id": uid, "count": cnt} for uid, cnt in sorted_items]

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _conversion_rate(customers: list[Customer]) -> float:
        if not customers:
            return 0.0
        closed = sum(1 for c in customers if c.pipeline_stage == "Closed Won")
        return round(closed / len(customers) * 100, 2)

    @staticmethod
    def _new_this_period(customers: list[Customer], days: int) -> int:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return sum(1 for c in customers if c.created_at and c.created_at >= cutoff)
