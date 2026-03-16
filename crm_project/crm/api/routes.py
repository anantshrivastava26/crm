"""
crm/api/routes.py
REST API — mobile-friendly, responsive JSON endpoints.
Jira refs: CRMS-50 (API integration layer), CRMS-46 (third-party integrations),
           CRMS-70 (mobile CRM access), CRMS-71 (responsive UI — served via API)
"""

from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm import Session
from crm.models.customer import Customer
from crm.services.auth_service import AuthService
from crm.services.analytics_service import AnalyticsService
from crm.services.segmentation_service import SegmentationService
from crm.services.workflow_service import WorkflowService
from crm.services.backup_service import BackupService
from crm.services.config_service import ConfigService
from crm.utils.validators import validate_email, validate_required

api = Blueprint("api", __name__, url_prefix="/api/v1")

# Config service is stateless, shared globally
_config_svc = ConfigService()


def _db() -> Session:
    return g.db


def _auth() -> AuthService:
    return AuthService(_db())


def _token() -> str:
    return request.headers.get("X-Auth-Token", "")


def _require(permission: str):
    _auth().require_permission(_token(), permission)


# ------------------------------------------------------------------ #
# Auth  (CRMS-38)
# ------------------------------------------------------------------ #
@api.post("/auth/register")
def register():
    data = request.json or {}
    missing = validate_required(data, ["username", "email", "password"])
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400
    if not validate_email(data["email"]):
        return jsonify({"error": "Invalid email."}), 400
    user = _auth().register(data["username"], data["email"], data["password"])
    return jsonify(user.to_dict()), 201


@api.post("/auth/login")
def login():
    data = request.json or {}
    token = _auth().login(data.get("email", ""), data.get("password", ""), request.remote_addr)
    return jsonify({"token": token})


@api.post("/auth/logout")
def logout():
    _auth().logout(_token())
    return jsonify({"message": "Logged out."})


# ------------------------------------------------------------------ #
# Customers
# ------------------------------------------------------------------ #
@api.get("/customers")
def list_customers():
    _require("read")
    stage = request.args.get("stage")
    segment = request.args.get("segment")
    tag = request.args.get("tag")
    seg_svc = SegmentationService(_db())
    if segment:
        customers = seg_svc.filter_by_segment(segment)
    elif tag:
        customers = seg_svc.filter_by_tag(tag)
    elif stage:
        customers = seg_svc.filter_by_stage(stage)
    else:
        customers = _db().query(Customer).all()
    return jsonify([c.to_dict() for c in customers])


@api.post("/customers")
def create_customer():
    _require("write")
    data = request.json or {}
    missing = validate_required(data, ["name", "email"])
    if missing:
        return jsonify({"error": f"Missing: {missing}"}), 400
    if not validate_email(data["email"]):
        return jsonify({"error": "Invalid email."}), 400

    c = Customer(
        name=data["name"],
        email=data["email"],
        phone=data.get("phone"),
        company=data.get("company"),
        pipeline_stage=data.get("pipeline_stage", "Lead"),
        segment=data.get("segment"),
        tags=data.get("tags", []),
        notes=data.get("notes"),
    )
    _db().add(c)
    _db().commit()

    # Fire workflow  (CRMS-59, CRMS-61)
    WorkflowService(_db()).fire("customer.created", c)
    return jsonify(c.to_dict()), 201


@api.get("/customers/<int:cid>")
def get_customer(cid: int):
    _require("read")
    c = _db().query(Customer).filter_by(id=cid).first()
    if not c:
        return jsonify({"error": "Not found."}), 404
    return jsonify(c.to_dict())


@api.put("/customers/<int:cid>")
def update_customer(cid: int):
    _require("write")
    c = _db().query(Customer).filter_by(id=cid).first()
    if not c:
        return jsonify({"error": "Not found."}), 404
    data = request.json or {}
    old_stage = c.pipeline_stage
    for field in ("name", "phone", "company", "pipeline_stage", "segment", "tags", "notes"):
        if field in data:
            setattr(c, field, data[field])
    _db().commit()
    if data.get("pipeline_stage") and data["pipeline_stage"] != old_stage:
        WorkflowService(_db()).fire("stage.changed", c)
    return jsonify(c.to_dict())


@api.delete("/customers/<int:cid>")
def delete_customer(cid: int):
    _require("delete")
    c = _db().query(Customer).filter_by(id=cid).first()
    if not c:
        return jsonify({"error": "Not found."}), 404
    _db().delete(c)
    _db().commit()
    return jsonify({"message": "Deleted."})


# ------------------------------------------------------------------ #
# Analytics  (CRMS-75, CRMS-78, CRMS-79, CRMS-80)
# ------------------------------------------------------------------ #
@api.get("/analytics/dashboard")
def dashboard():
    _require("read")
    return jsonify(AnalyticsService(_db()).dashboard_summary())


@api.get("/analytics/pipeline")
def pipeline():
    _require("read")
    return jsonify(AnalyticsService(_db()).pipeline_velocity())


@api.get("/analytics/leads-over-time")
def leads_over_time():
    _require("read")
    days = int(request.args.get("days", 30))
    return jsonify(AnalyticsService(_db()).leads_over_time(days))


# ------------------------------------------------------------------ #
# Segmentation  (CRMS-64–69)
# ------------------------------------------------------------------ #
@api.post("/customers/<int:cid>/tags")
def add_tag(cid: int):
    _require("write")
    tag = (request.json or {}).get("tag", "")
    if not tag:
        return jsonify({"error": "tag required."}), 400
    c = SegmentationService(_db()).add_tag(cid, tag)
    return jsonify(c.to_dict())


@api.delete("/customers/<int:cid>/tags/<tag>")
def remove_tag(cid: int, tag: str):
    _require("write")
    c = SegmentationService(_db()).remove_tag(cid, tag)
    return jsonify(c.to_dict())


@api.get("/tags")
def list_tags():
    _require("read")
    return jsonify(SegmentationService(_db()).list_all_tags())


# ------------------------------------------------------------------ #
# Backup & health  (CRMS-84, CRMS-85, CRMS-86)
# ------------------------------------------------------------------ #
@api.get("/health")
def health():
    return jsonify(BackupService(_db()).health_check())


@api.post("/backup")
def create_backup():
    _require("admin")
    path = BackupService(_db()).create_backup()
    return jsonify({"message": "Backup created.", "path": path})


@api.post("/backup/restore")
def restore_backup():
    _require("admin")
    filename = (request.json or {}).get("filename", "")
    result = BackupService(_db()).restore_from_backup(filename)
    return jsonify(result)


# ------------------------------------------------------------------ #
# System config  (CRMS-81–83)
# ------------------------------------------------------------------ #
@api.get("/config/settings")
def get_settings():
    _require("read")
    return jsonify(_config_svc.get_settings_snapshot())


@api.put("/config/pipeline-stages")
def update_pipeline():
    _require("admin")
    stages = (request.json or {}).get("stages", [])
    _config_svc.set_pipeline_stages(stages)
    return jsonify({"pipeline_stages": _config_svc.get_pipeline_stages()})
