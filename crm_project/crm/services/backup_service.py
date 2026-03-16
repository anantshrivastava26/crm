"""
crm/services/backup_service.py
Scheduled DB backup, restore, and health monitoring.
Jira refs: CRMS-77 (Backup, Recovery & Reliability), CRMS-84 (backup scheduling),
           CRMS-85 (restore mechanisms), CRMS-86 (health monitoring)
"""

from __future__ import annotations
import os
import json
import shutil
import schedule
import time
import threading
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from crm.models.customer import Customer
from crm.models.user import User
from crm.models.audit_log import AuditLog
from config.settings import get_config

cfg = get_config()


class BackupService:
    def __init__(self, db: Session):
        self.db = db
        os.makedirs(cfg.BACKUP_DIR, exist_ok=True)
        self._scheduler_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ #
    # Backup  (CRMS-84)
    # ------------------------------------------------------------------ #
    def create_backup(self, label: Optional[str] = None) -> str:
        """Dump all tables to a JSON backup file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{label or timestamp}.json"
        filepath = os.path.join(cfg.BACKUP_DIR, filename)

        data = {
            "created_at": datetime.utcnow().isoformat(),
            "customers": [c.to_dict() for c in self.db.query(Customer).all()],
            "users": [u.to_dict() for u in self.db.query(User).all()],
            "audit_logs": [a.to_dict() for a in self.db.query(AuditLog).all()],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        return filepath

    def list_backups(self) -> list[dict]:
        files = [
            f for f in os.listdir(cfg.BACKUP_DIR)
            if f.startswith("backup_") and f.endswith(".json")
        ]
        result = []
        for fname in sorted(files, reverse=True):
            fpath = os.path.join(cfg.BACKUP_DIR, fname)
            stat = os.stat(fpath)
            result.append({
                "filename": fname,
                "size_kb": round(stat.st_size / 1024, 1),
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })
        return result

    # ------------------------------------------------------------------ #
    # Restore  (CRMS-85)
    # ------------------------------------------------------------------ #
    def restore_from_backup(self, filename: str) -> dict:
        """
        Restore customers from a backup file.
        WARNING: This merges data — it does NOT wipe the existing DB.
        For full restore, clear tables first.
        """
        filepath = os.path.join(cfg.BACKUP_DIR, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Backup file '{filename}' not found.")

        with open(filepath) as f:
            data = json.load(f)

        restored = 0
        skipped = 0
        for row in data.get("customers", []):
            if self.db.query(Customer).filter_by(email=row["email"]).first():
                skipped += 1
                continue
            c = Customer(
                name=row["name"],
                email=row["email"],
                phone=row.get("phone"),
                company=row.get("company"),
                pipeline_stage=row.get("pipeline_stage"),
                segment=row.get("segment"),
                tags=row.get("tags", []),
                notes=row.get("notes"),
            )
            self.db.add(c)
            restored += 1

        self.db.commit()
        return {"restored": restored, "skipped": skipped, "source": filename}

    # ------------------------------------------------------------------ #
    # Scheduled backups  (CRMS-84)
    # ------------------------------------------------------------------ #
    def start_scheduler(self) -> None:
        """Run daily backup at the configured hour in a background thread."""
        schedule.every().day.at(f"{cfg.BACKUP_SCHEDULE_HOUR:02d}:00").do(self.create_backup)

        def _run():
            while True:
                schedule.run_pending()
                time.sleep(60)

        self._scheduler_thread = threading.Thread(target=_run, daemon=True)
        self._scheduler_thread.start()

    # ------------------------------------------------------------------ #
    # Health monitoring  (CRMS-86)
    # ------------------------------------------------------------------ #
    def health_check(self) -> dict:
        """Return a health status dict for monitoring dashboards."""
        try:
            customer_count = self.db.query(Customer).count()
            db_status = "healthy"
        except Exception as e:
            customer_count = -1
            db_status = f"error: {e}"

        backups = self.list_backups()
        latest_backup = backups[0]["created_at"] if backups else None

        return {
            "status": "ok" if db_status == "healthy" else "degraded",
            "db": db_status,
            "customer_count": customer_count,
            "backup_count": len(backups),
            "latest_backup": latest_backup,
            "checked_at": datetime.utcnow().isoformat(),
        }
