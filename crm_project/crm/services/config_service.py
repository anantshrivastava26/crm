"""
crm/services/config_service.py
Runtime system configuration, custom fields, and configurable pipelines.
Jira refs: CRMS-81 (custom fields module), CRMS-82 (configurable pipelines),
           CRMS-83 (settings UI data)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from config.settings import get_config

cfg = get_config()


@dataclass
class CustomField:
    name: str
    field_type: str           # "text", "number", "date", "select"
    required: bool = False
    options: list[str] = field(default_factory=list)   # for "select" type
    default: Optional[Any] = None


class ConfigService:
    def __init__(self):
        self._pipeline_stages: list[str] = list(cfg.PIPELINE_STAGES)
        self._custom_fields: dict[str, CustomField] = {}

    # ------------------------------------------------------------------ #
    # Pipeline stages  (CRMS-82)
    # ------------------------------------------------------------------ #
    def get_pipeline_stages(self) -> list[str]:
        return list(self._pipeline_stages)

    def set_pipeline_stages(self, stages: list[str]) -> None:
        if len(stages) < 2:
            raise ValueError("Pipeline must have at least 2 stages.")
        self._pipeline_stages = [s.strip() for s in stages if s.strip()]

    def add_stage(self, stage: str, position: Optional[int] = None) -> list[str]:
        stage = stage.strip()
        if stage in self._pipeline_stages:
            raise ValueError(f"Stage '{stage}' already exists.")
        if position is None:
            self._pipeline_stages.append(stage)
        else:
            self._pipeline_stages.insert(position, stage)
        return self._pipeline_stages

    def remove_stage(self, stage: str) -> list[str]:
        if stage not in self._pipeline_stages:
            raise ValueError(f"Stage '{stage}' not found.")
        self._pipeline_stages.remove(stage)
        return self._pipeline_stages

    # ------------------------------------------------------------------ #
    # Custom fields  (CRMS-81)
    # ------------------------------------------------------------------ #
    def register_custom_field(self, field_def: CustomField) -> CustomField:
        self._custom_fields[field_def.name] = field_def
        return field_def

    def remove_custom_field(self, name: str) -> None:
        self._custom_fields.pop(name, None)

    def get_custom_fields(self) -> list[CustomField]:
        return list(self._custom_fields.values())

    def validate_custom_fields(self, data: dict) -> dict:
        """CRMS-81: Validate a dict of custom-field values against registered fields."""
        errors = {}
        for fname, fdef in self._custom_fields.items():
            val = data.get(fname)
            if fdef.required and (val is None or val == ""):
                errors[fname] = "This field is required."
            if val and fdef.field_type == "select" and val not in fdef.options:
                errors[fname] = f"Must be one of: {fdef.options}"
            if val and fdef.field_type == "number":
                try:
                    float(val)
                except (TypeError, ValueError):
                    errors[fname] = "Must be a number."
        return errors

    # ------------------------------------------------------------------ #
    # Settings snapshot  (CRMS-83)
    # ------------------------------------------------------------------ #
    def get_settings_snapshot(self) -> dict:
        return {
            "pipeline_stages": self._pipeline_stages,
            "custom_fields": [
                {
                    "name": f.name,
                    "type": f.field_type,
                    "required": f.required,
                    "options": f.options,
                    "default": f.default,
                }
                for f in self._custom_fields.values()
            ],
        }
