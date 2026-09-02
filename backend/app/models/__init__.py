"""Import all models so SQLAlchemy registers them with Base.metadata."""
from app.models.base import (  # noqa: F401
    User,
    Inspection,
    InspectionImage,
    ExtractedField,
    Violation,
    Report,
    RulePack,
    AuditLog,
)
