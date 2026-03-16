"""
main.py
Application entry point — creates the Flask app, sets up DB, and starts the server.
"""

from flask import Flask, g
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from crm.models.base import Base
from crm.models.customer import Customer   # noqa: F401 — register models
from crm.models.user import User           # noqa: F401
from crm.models.audit_log import AuditLog  # noqa: F401
from crm.api.routes import api
from crm.services.backup_service import BackupService
from config.settings import get_config

cfg = get_config()

# ------------------------------------------------------------------ #
# DB setup
# ------------------------------------------------------------------ #
engine = create_engine(cfg.DATABASE_URL, echo=cfg.DEBUG)
SessionLocal = sessionmaker(bind=engine)


def create_app() -> Flask:
    Base.metadata.create_all(engine)

    app = Flask(__name__)
    app.secret_key = cfg.SECRET_KEY
    app.register_blueprint(api)

    @app.before_request
    def open_db():
        g.db = SessionLocal()

    @app.teardown_appcontext
    def close_db(exc=None):
        db = g.pop("db", None)
        if db:
            db.close()

    return app


if __name__ == "__main__":
    app = create_app()

    # Start scheduled backup in background  (CRMS-84)
    with app.app_context():
        from flask import g as app_g
        db_session = SessionLocal()
        BackupService(db_session).start_scheduler()
        db_session.close()

    print("🚀  CRM API running — http://localhost:5000/api/v1/health")
    app.run(host="0.0.0.0", port=5000, debug=cfg.DEBUG)
