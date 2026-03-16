"""
config/settings.py
App-wide configuration — load from environment or use defaults.
Jira ref: CRMS-81 (Custom fields module), CRMS-82 (Configurable pipelines), CRMS-83 (Settings UI)
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///crm.db")
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

    # Session
    SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", 30))

    # Backup
    BACKUP_DIR = os.getenv("BACKUP_DIR", "backups/")
    BACKUP_SCHEDULE_HOUR = int(os.getenv("BACKUP_SCHEDULE_HOUR", 2))  # 2 AM

    # Export
    EXPORT_DIR = os.getenv("EXPORT_DIR", "exports/")
    ALLOWED_EXPORT_FORMATS = ["csv", "pdf"]

    # Pipeline stages (configurable — CRMS-82)
    PIPELINE_STAGES = os.getenv(
        "PIPELINE_STAGES", "Lead,Contacted,Qualified,Proposal,Closed Won,Closed Lost"
    ).split(",")

    # Custom fields (CRMS-81)
    CUSTOM_FIELDS: list[dict] = []


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


def get_config() -> Config:
    env = os.getenv("APP_ENV", "development")
    return ProductionConfig() if env == "production" else DevelopmentConfig()
