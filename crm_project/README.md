# Customer Relationship Management (CRM) System

A Python-based CRM system built from the Jira project **CRMS** on `srmist-team-vv1tegy9.atlassian.net`.

## Epics Covered

| Epic | Key Modules |
|------|-------------|
| Data Import, Export & Integration | `services/import_service.py`, `services/export_service.py` |
| Security, Audit & Compliance | `services/auth_service.py`, `services/audit_service.py` |
| Workflow Automation | `services/workflow_service.py` |
| Customer Segmentation & Tagging | `services/segmentation_service.py` |
| Analytics, Dashboards & KPIs | `services/analytics_service.py` |
| System Configuration & Customization | `services/config_service.py` |
| Backup, Recovery & Reliability | `services/backup_service.py` |
| Mobile & Responsive CRM | `api/routes.py` (REST API) |

## Project Structure

```
crm_project/
├── crm/
│   ├── models/           # SQLAlchemy ORM models
│   │   ├── customer.py
│   │   ├── lead.py
│   │   ├── user.py
│   │   └── audit_log.py
│   ├── services/         # Business logic services
│   │   ├── auth_service.py
│   │   ├── audit_service.py
│   │   ├── import_service.py
│   │   ├── export_service.py
│   │   ├── workflow_service.py
│   │   ├── segmentation_service.py
│   │   ├── analytics_service.py
│   │   ├── config_service.py
│   │   └── backup_service.py
│   ├── api/              # REST API routes (Flask)
│   │   └── routes.py
│   └── utils/            # Helpers and utilities
│       ├── validators.py
│       └── helpers.py
├── tests/                # Unit tests
├── config/               # App configuration
│   └── settings.py
├── scripts/              # Utility scripts
│   └── seed_data.py
├── requirements.txt
└── main.py
```

## Setup

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Jira Traceability

Each module maps to Jira issues in the CRMS project:
- **CRMS-44 to 50**: Import/Export & Integration
- **CRMS-51 to 57**: Security, Audit & Compliance
- **CRMS-58 to 63**: Workflow Automation
- **CRMS-64 to 69**: Segmentation & Tagging
- **CRMS-78 to 80**: Analytics & Dashboard
- **CRMS-81 to 83**: Config & Customization
- **CRMS-84 to 86**: Backup & Recovery
