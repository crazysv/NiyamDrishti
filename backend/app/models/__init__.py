"""Import all models so SQLAlchemy registers them with Base.metadata."""

from app.models.base import (  # noqa: F401
    AuditLog,
    ExtractedField,
    Inspection,
    InspectionImage,
    Report,
    RulePack,
    User,
    Violation,
)
