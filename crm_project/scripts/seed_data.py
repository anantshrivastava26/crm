"""
scripts/seed_data.py
Populate the DB with sample data for development/demo.
Run: python -m scripts.seed_data
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from crm.models.base import Base
from crm.models.customer import Customer
from crm.models.user import User, Role
from crm.models.audit_log import AuditLog  # noqa
from crm.services.auth_service import AuthService
from config.settings import get_config

cfg = get_config()
engine = create_engine(cfg.DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

auth = AuthService(db)

# Create users
try:
    admin = auth.register("admin", "admin@crm.local", "Admin@1234!", Role.ADMIN)
    mgr   = auth.register("manager", "manager@crm.local", "Mgr@1234!", Role.MANAGER)
    exec1 = auth.register("alice", "alice@crm.local", "Alice@1234!", Role.SALES_EXEC)
    print(f"Created users: {admin.username}, {mgr.username}, {exec1.username}")
except ValueError as e:
    print(f"Users already exist: {e}")
    exec1 = db.query(User).filter_by(username="alice").first()

# Create sample customers
customers = [
    Customer(name="Acme Corp", email="contact@acme.com", company="Acme Inc", pipeline_stage="Lead", segment="Enterprise", tags=["hot"]),
    Customer(name="John Doe", email="john@example.com", phone="555-1234", company="Doe LLC", pipeline_stage="Contacted", segment="SMB"),
    Customer(name="Sara Smith", email="sara@widgets.com", company="Widgets Ltd", pipeline_stage="Qualified", tags=["vip", "follow-up"]),
    Customer(name="TechStart", email="hello@techstart.io", company="TechStart Inc", pipeline_stage="Proposal"),
    Customer(name="Global Retail", email="sales@globalretail.com", company="Global Retail Inc", pipeline_stage="Closed Won", segment="Enterprise"),
    Customer(name="MiniShop", email="owner@minishop.net", pipeline_stage="Closed Lost"),
]
for c in customers:
    if not db.query(Customer).filter_by(email=c.email).first():
        if exec1:
            c.assigned_to = exec1.id
        db.add(c)

db.commit()
print(f"Seeded {len(customers)} customers.")
db.close()
