"""
tests/test_crm.py
Unit tests covering auth, segmentation, analytics, workflow, and config services.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from crm.models.base import Base
from crm.models.customer import Customer
from crm.models.user import User, Role
from crm.models.audit_log import AuditLog  # noqa
from crm.services.auth_service import AuthService
from crm.services.segmentation_service import SegmentationService, SegmentRule
from crm.services.analytics_service import AnalyticsService
from crm.services.workflow_service import WorkflowService, WorkflowRule
from crm.services.config_service import ConfigService, CustomField


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #
@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def user(db):
    auth = AuthService(db)
    return auth.register("testuser", "test@crm.local", "Test@1234!")


@pytest.fixture
def customer(db, user):
    c = Customer(
        name="Test Corp",
        email="corp@test.com",
        company="Test Inc",
        pipeline_stage="Lead",
        segment="SMB",
        tags=["test"],
        assigned_to=user.id,
    )
    db.add(c)
    db.commit()
    return c


# ------------------------------------------------------------------ #
# Auth tests
# ------------------------------------------------------------------ #
class TestAuth:
    def test_register_success(self, db):
        auth = AuthService(db)
        u = auth.register("newuser", "new@crm.local", "Pass@1234!")
        assert u.id is not None
        assert u.role == Role.SALES_EXEC

    def test_register_duplicate_email(self, db, user):
        auth = AuthService(db)
        with pytest.raises(ValueError, match="already registered"):
            auth.register("other", "test@crm.local", "pass")

    def test_login_success(self, db, user):
        auth = AuthService(db)
        token = auth.login("test@crm.local", "Test@1234!")
        assert isinstance(token, str) and len(token) > 10

    def test_login_wrong_password(self, db, user):
        auth = AuthService(db)
        with pytest.raises(PermissionError):
            auth.login("test@crm.local", "wrongpass")

    def test_permission_granted(self, db, user):
        auth = AuthService(db)
        token = auth.login("test@crm.local", "Test@1234!")
        assert auth.has_permission(token, "read") is True
        assert auth.has_permission(token, "write") is True

    def test_permission_denied(self, db, user):
        auth = AuthService(db)
        token = auth.login("test@crm.local", "Test@1234!")
        assert auth.has_permission(token, "admin") is False

    def test_logout_invalidates_token(self, db, user):
        auth = AuthService(db)
        token = auth.login("test@crm.local", "Test@1234!")
        auth.logout(token)
        assert auth.get_session(token) is None


# ------------------------------------------------------------------ #
# Segmentation tests
# ------------------------------------------------------------------ #
class TestSegmentation:
    def test_add_tag(self, db, customer):
        svc = SegmentationService(db)
        updated = svc.add_tag(customer.id, "vip")
        assert "vip" in updated.tags

    def test_remove_tag(self, db, customer):
        svc = SegmentationService(db)
        updated = svc.remove_tag(customer.id, "test")
        assert "test" not in updated.tags

    def test_filter_by_segment(self, db, customer):
        svc = SegmentationService(db)
        results = svc.filter_by_segment("SMB")
        assert any(c.id == customer.id for c in results)

    def test_filter_by_tag(self, db, customer):
        svc = SegmentationService(db)
        results = svc.filter_by_tag("test")
        assert any(c.id == customer.id for c in results)

    def test_classify_customer(self, db, customer):
        svc = SegmentationService(db)
        svc.add_segment_rule(SegmentRule(
            segment_name="TestSegment",
            conditions=[{"field": "company", "op": "contains", "value": "test"}],
        ))
        seg = svc.classify_customer(customer)
        assert seg == "TestSegment"


# ------------------------------------------------------------------ #
# Analytics tests
# ------------------------------------------------------------------ #
class TestAnalytics:
    def test_dashboard_summary_keys(self, db, customer):
        svc = AnalyticsService(db)
        summary = svc.dashboard_summary()
        for key in ("total_customers", "by_stage", "by_segment", "conversion_rate"):
            assert key in summary

    def test_pipeline_velocity(self, db, customer):
        svc = AnalyticsService(db)
        pv = svc.pipeline_velocity()
        assert "Lead" in pv

    def test_conversion_rate_zero(self, db, customer):
        svc = AnalyticsService(db)
        assert svc.conversion_rate() == 0.0


# ------------------------------------------------------------------ #
# Workflow tests
# ------------------------------------------------------------------ #
class TestWorkflow:
    def test_fire_matching_rule(self, db, customer):
        svc = WorkflowService(db)
        svc.add_rule(WorkflowRule(
            id="test_stage",
            name="Set stage to Contacted",
            trigger="customer.created",
            conditions=[{"field": "segment", "op": "eq", "value": "SMB"}],
            actions=[{"type": "set_stage", "stage": "Contacted"}],
        ))
        executed = svc.fire("customer.created", customer)
        assert any("Contacted" in e for e in executed)

    def test_fire_non_matching_rule(self, db, customer):
        svc = WorkflowService(db)
        executed = svc.fire("customer.created", customer, {"segment": "VIP"})
        # Default VIP rule should not match SMB customer
        assert not any("user 1" in e for e in executed)


# ------------------------------------------------------------------ #
# Config tests
# ------------------------------------------------------------------ #
class TestConfig:
    def test_pipeline_stages(self):
        svc = ConfigService()
        stages = svc.get_pipeline_stages()
        assert len(stages) >= 2

    def test_add_remove_stage(self):
        svc = ConfigService()
        svc.add_stage("Negotiation")
        assert "Negotiation" in svc.get_pipeline_stages()
        svc.remove_stage("Negotiation")
        assert "Negotiation" not in svc.get_pipeline_stages()

    def test_custom_field_validation(self):
        svc = ConfigService()
        svc.register_custom_field(CustomField(name="priority", field_type="select", options=["High", "Low"], required=True))
        errors = svc.validate_custom_fields({})
        assert "priority" in errors
        errors = svc.validate_custom_fields({"priority": "High"})
        assert "priority" not in errors
