"""
crm/services/export_service.py
Export sales reports to CSV and PDF.
Jira refs: CRMS-45 (export sales reports), CRMS-49 (export reports PDF/CSV),
           CRMS-37 (filter reports by date range)
"""

import os
import csv
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from crm.models.customer import Customer
from config.settings import get_config

cfg = get_config()


class ExportService:
    def __init__(self, db: Session):
        self.db = db
        os.makedirs(cfg.EXPORT_DIR, exist_ok=True)

    # ------------------------------------------------------------------ #
    # CSV  (CRMS-49)
    # ------------------------------------------------------------------ #
    def export_csv(
        self,
        filename: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        """Export customers to CSV with optional date filter (CRMS-37)."""
        customers = self._query_customers(start_date, end_date)
        filepath = os.path.join(cfg.EXPORT_DIR, filename or f"customers_{self._ts()}.csv")

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "name", "email", "phone", "company",
                "pipeline_stage", "segment", "tags", "assigned_to", "created_at",
            ])
            writer.writeheader()
            for c in customers:
                row = c.to_dict()
                row["tags"] = ", ".join(row.get("tags") or [])
                writer.writerow({k: row.get(k, "") for k in writer.fieldnames})

        return filepath

    # ------------------------------------------------------------------ #
    # PDF  (CRMS-49)
    # ------------------------------------------------------------------ #
    def export_pdf(
        self,
        filename: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        """Export customers to a formatted PDF report."""
        customers = self._query_customers(start_date, end_date)
        filepath = os.path.join(cfg.EXPORT_DIR, filename or f"report_{self._ts()}.pdf")
        styles = getSampleStyleSheet()

        doc = SimpleDocTemplate(filepath, pagesize=A4)
        elements = []

        elements.append(Paragraph("CRM — Customer Report", styles["Title"]))
        elements.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC", styles["Normal"]))
        elements.append(Spacer(1, 12))

        headers = ["ID", "Name", "Email", "Company", "Stage", "Segment"]
        rows = [headers] + [
            [c.id, c.name, c.email, c.company or "", c.pipeline_stage or "", c.segment or ""]
            for c in customers
        ]

        table = Table(rows, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0052CC")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F5F7")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DFE1E6")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        elements.append(table)
        doc.build(elements)
        return filepath

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _query_customers(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> list[Customer]:
        q = self.db.query(Customer)
        if start_date:
            q = q.filter(Customer.created_at >= start_date)
        if end_date:
            q = q.filter(Customer.created_at <= end_date)
        return q.all()

    @staticmethod
    def _ts() -> str:
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S")
