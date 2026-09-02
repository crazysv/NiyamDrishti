"""
SQLAlchemy models — must match 06_SCHEMA.md exactly.
UUID primary keys use server_default=text("gen_random_uuid()") for Postgres
and a Python-side default (uuid4) for SQLite compatibility.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, DateTime, Index, Integer, Numeric, String, Text,
    ForeignKey, func, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# ---------------------------------------------------------------------------
# Cross-dialect UUID type (Postgres: native UUID; SQLite: CHAR(36))
# ---------------------------------------------------------------------------
class UUID(TypeDecorator):
    """Platform-independent UUID type."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value)


# ---------------------------------------------------------------------------
# Cross-dialect JSON type (Postgres: JSONB; SQLite: Text stored as JSON)
# ---------------------------------------------------------------------------
from sqlalchemy import JSON


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id:             Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    email:          Mapped[str]        = mapped_column(Text, nullable=False, unique=True)
    password_hash:  Mapped[str]        = mapped_column(Text, nullable=False)
    full_name:      Mapped[str]        = mapped_column(Text, nullable=False)
    role:           Mapped[str]        = mapped_column(Text, nullable=False)
    region:         Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active:      Mapped[bool]       = mapped_column(Boolean, nullable=False, default=True)
    created_at:     Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:     Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('officer', 'supervisor', 'admin')", name="ck_users_role"),
    )

    inspections: Mapped[list["Inspection"]] = relationship(back_populates="officer")


# ---------------------------------------------------------------------------
# inspections
# ---------------------------------------------------------------------------
class Inspection(Base):
    __tablename__ = "inspections"

    id:                  Mapped[uuid.UUID]       = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    officer_id:          Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    status:              Mapped[str]              = mapped_column(Text, nullable=False, default="draft")
    commodity_category:  Mapped[str | None]       = mapped_column(Text, nullable=True)
    rule_pack_version:   Mapped[str]              = mapped_column(Text, nullable=False)  # frozen at creation
    is_self_check:       Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    region:              Mapped[str | None]        = mapped_column(Text, nullable=True)
    captured_offline:    Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    created_at:          Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:          Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    synced_at:           Mapped[datetime | None]   = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','processing','needs_review','completed','sync_pending')",
            name="ck_inspections_status"
        ),
        Index("idx_inspections_officer", "officer_id"),
        Index("idx_inspections_status", "status"),
        Index("idx_inspections_created", "created_at"),
    )

    officer:  Mapped["User"]                    = relationship(back_populates="inspections")
    images:   Mapped[list["InspectionImage"]]   = relationship(back_populates="inspection", cascade="all, delete-orphan")
    fields:   Mapped[list["ExtractedField"]]    = relationship(back_populates="inspection", cascade="all, delete-orphan")
    violations: Mapped[list["Violation"]]       = relationship(back_populates="inspection", cascade="all, delete-orphan")
    reports:  Mapped[list["Report"]]            = relationship(back_populates="inspection", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# inspection_images
# ---------------------------------------------------------------------------
class InspectionImage(Base):
    __tablename__ = "inspection_images"

    id:               Mapped[uuid.UUID]       = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    inspection_id:    Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False)
    image_role:       Mapped[str]              = mapped_column(Text, nullable=False)
    storage_url:      Mapped[str]              = mapped_column(Text, nullable=False)
    width_px:         Mapped[int | None]       = mapped_column(Integer, nullable=True)
    height_px:        Mapped[int | None]       = mapped_column(Integer, nullable=True)
    calibration_scale_mm_per_px: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    quality_check_passed: Mapped[bool]         = mapped_column(Boolean, nullable=False, default=False)
    captured_at:      Mapped[datetime]         = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_at:      Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "image_role IN ('front_pdp','back_panel','side_panel','sticker','ecommerce_listing')",
            name="ck_images_role"
        ),
        Index("idx_images_inspection", "inspection_id"),
    )

    inspection: Mapped["Inspection"] = relationship(back_populates="images")


# ---------------------------------------------------------------------------
# extracted_fields
# ---------------------------------------------------------------------------
class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id:                    Mapped[uuid.UUID]       = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    inspection_id:         Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False)
    source_image_id:       Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey("inspection_images.id"), nullable=False)
    field_type:            Mapped[str]              = mapped_column(Text, nullable=False)
    raw_text:              Mapped[str | None]        = mapped_column(Text, nullable=True)
    parsed_value:          Mapped[str | None]        = mapped_column(Text, nullable=True)
    confidence:            Mapped[float]             = mapped_column(Numeric, nullable=False)
    bounding_box:          Mapped[dict]              = mapped_column(JSON, nullable=False)  # {x, y, w, h}
    verdict:               Mapped[str]              = mapped_column(Text, nullable=False)
    reviewed_by_officer:   Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    officer_override_value: Mapped[str | None]      = mapped_column(Text, nullable=True)
    created_at:            Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "verdict IN ('pass','fail','needs_review','not_applicable')",
            name="ck_fields_verdict"
        ),
        Index("idx_fields_inspection", "inspection_id"),
        Index("idx_fields_verdict", "verdict"),
    )

    inspection: Mapped["Inspection"] = relationship(back_populates="fields")


# ---------------------------------------------------------------------------
# violations
# ---------------------------------------------------------------------------
class Violation(Base):
    __tablename__ = "violations"

    id:                  Mapped[uuid.UUID]       = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    inspection_id:       Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False)
    extracted_field_id:  Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("extracted_fields.id"), nullable=True)
    rule_id:             Mapped[str]              = mapped_column(Text, nullable=False)
    rule_pack_version:   Mapped[str]              = mapped_column(Text, nullable=False)
    description:         Mapped[str]              = mapped_column(Text, nullable=False)
    citation:            Mapped[str | None]        = mapped_column(Text, nullable=True)
    severity:            Mapped[str]              = mapped_column(Text, nullable=False)
    created_at:          Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("severity IN ('minor','major','critical')", name="ck_violations_severity"),
        Index("idx_violations_inspection", "inspection_id"),
        Index("idx_violations_rule", "rule_id"),
    )

    inspection: Mapped["Inspection"] = relationship(back_populates="violations")


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------
class Report(Base):
    __tablename__ = "reports"

    id:             Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    inspection_id:  Mapped[uuid.UUID]  = mapped_column(UUID, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False)
    format:         Mapped[str]        = mapped_column(Text, nullable=False)
    storage_url:    Mapped[str]        = mapped_column(Text, nullable=False)
    generated_by:   Mapped[uuid.UUID]  = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    generated_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("format IN ('pdf','editable')", name="ck_reports_format"),
        Index("idx_reports_inspection", "inspection_id"),
    )

    inspection: Mapped["Inspection"] = relationship(back_populates="reports")


# ---------------------------------------------------------------------------
# rule_packs
# ---------------------------------------------------------------------------
class RulePack(Base):
    __tablename__ = "rule_packs"

    version:          Mapped[str]              = mapped_column(Text, primary_key=True)
    effective_from:   Mapped[datetime]          = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to:     Mapped[datetime | None]   = mapped_column(DateTime(timezone=True), nullable=True)
    source_citation:  Mapped[str | None]        = mapped_column(Text, nullable=True)
    rules_json:       Mapped[dict]              = mapped_column(JSON, nullable=False)
    is_active:        Mapped[bool]              = mapped_column(Boolean, nullable=False, default=False)
    created_by:       Mapped[uuid.UUID]         = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    created_at:       Mapped[datetime]           = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# audit_logs  (append-only — no UPDATE or DELETE ever)
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id:             Mapped[uuid.UUID]       = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    actor_user_id:  Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    action:         Mapped[str]              = mapped_column(Text, nullable=False)
    entity_type:    Mapped[str]              = mapped_column(Text, nullable=False)
    entity_id:      Mapped[str]              = mapped_column(Text, nullable=False)
    before_value:   Mapped[dict | None]      = mapped_column(JSON, nullable=True)
    after_value:    Mapped[dict | None]      = mapped_column(JSON, nullable=True)
    created_at:     Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_actor", "actor_user_id"),
    )
