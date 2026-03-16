"""
crm/services/import_service.py
CSV / Excel import with data validation and mapping.
Jira refs: CRMS-44 (import customers from CSV/Excel),
           CRMS-47 (CSV/Excel upload module), CRMS-48 (data validation & mapping)
"""

import pandas as pd
from sqlalchemy.orm import Session
from crm.models.customer import Customer
from crm.utils.validators import validate_email


REQUIRED_COLUMNS = {"name", "email"}
OPTIONAL_COLUMNS = {"phone", "company", "pipeline_stage", "segment", "notes"}


class ImportService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def import_from_csv(self, filepath: str) -> dict:
        """CRMS-47: Import customers from a CSV file."""
        df = pd.read_csv(filepath)
        return self._process_dataframe(df, source=filepath)

    def import_from_excel(self, filepath: str, sheet: str = 0) -> dict:
        """CRMS-47: Import customers from an Excel file."""
        df = pd.read_excel(filepath, sheet_name=sheet)
        return self._process_dataframe(df, source=filepath)

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _process_dataframe(self, df: pd.DataFrame, source: str) -> dict:
        """CRMS-48: Validate, map, and persist rows."""
        df.columns = [c.strip().lower() for c in df.columns]
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        created, skipped, errors = 0, 0, []

        for idx, row in df.iterrows():
            try:
                row_dict = self._map_row(row)
                self._validate_row(row_dict, idx)

                if self.db.query(Customer).filter_by(email=row_dict["email"]).first():
                    skipped += 1
                    continue

                customer = Customer(**row_dict)
                self.db.add(customer)
                created += 1
            except (ValueError, KeyError) as e:
                errors.append({"row": idx + 2, "error": str(e)})

        self.db.commit()
        return {"created": created, "skipped": skipped, "errors": errors, "source": source}

    def _map_row(self, row: pd.Series) -> dict:
        """CRMS-48: Map CSV columns to model fields."""
        data = {
            "name": str(row.get("name", "")).strip(),
            "email": str(row.get("email", "")).strip().lower(),
        }
        for col in OPTIONAL_COLUMNS:
            if col in row and pd.notna(row[col]):
                data[col] = str(row[col]).strip()
        return data

    def _validate_row(self, data: dict, idx: int) -> None:
        """CRMS-48: Basic validation."""
        if not data.get("name"):
            raise ValueError(f"Row {idx + 2}: 'name' is required.")
        if not validate_email(data.get("email", "")):
            raise ValueError(f"Row {idx + 2}: invalid email '{data['email']}'.")
