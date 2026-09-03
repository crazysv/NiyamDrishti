"""
SQLAlchemy models â€” must match 06_SCHEMA.md exactly.
UUID primary keys use server_default=text("gen_random_uuid()") for Postgres
and a Python-side default (uuid4) for SQLite compatibility.
"""

import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text, event, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, TypeDecorator

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
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


# ---------------------------------------------------------------------------
# Cross-dialect JSON type (Postgres: JSONB; SQLite: Text stored as JSON)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (CheckConstraint("role IN ('officer', 'supervisor', 'admin')", name="ck_users_role"),)

    inspections: Mapped[list["Inspection"]] = relationship(back_populates="officer")
    batch_sessions: Mapped[list["BatchSession"]] = relationship(back_populates="officer")


# ---------------------------------------------------------------------------
# batch_sessions (E3-05)
# ---------------------------------------------------------------------------
class BatchSession(Base):
    __tablename__ = "batch_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    officer_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    session_name: Mapped[str] = mapped_column(Text, nullable=False)
    premises_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    premises_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'archived')", name="ck_batch_sessions_status"),
        Index("idx_batch_sessions_officer", "officer_id"),
        Index("idx_batch_sessions_status", "status"),
        Index("idx_batch_sessions_created", "created_at"),
    )

    officer: Mapped["User"] = relationship(back_populates="batch_sessions")
    inspections: Mapped[list["Inspection"]] = relationship(back_populates="batch")


# ---------------------------------------------------------------------------
# inspections
# ---------------------------------------------------------------------------
class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    officer_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("batch_sessions.id"), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    commodity_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_pack_version: Mapped[str] = mapped_column(Text, nullable=False)  # frozen at creation
    is_self_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    region: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_offline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    client_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','processing','needs_review','completed','sync_pending')", name="ck_inspections_status"
        ),
        Index("idx_inspections_officer", "officer_id"),
        Index("idx_inspections_batch", "batch_id"),
        Index("idx_inspections_status", "status"),
        Index("idx_inspections_created", "created_at"),
        Index("idx_inspections_client_id", "client_id"),
    )

    officer: Mapped["User"] = relationship(back_populates="inspections")
    batch: Mapped["BatchSession | None"] = relationship(back_populates="inspections")
    images: Mapped[list["InspectionImage"]] = relationship(back_populates="inspection", cascade="all, delete-orphan")
    fields: Mapped[list["ExtractedField"]] = relationship(back_populates="inspection", cascade="all, delete-orphan")
    violations: Mapped[list["Violation"]] = relationship(back_populates="inspection", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="inspection", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# inspection_images
# ---------------------------------------------------------------------------
class InspectionImage(Base):
    __tablename__ = "inspection_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False
    )
    image_role: Mapped[str] = mapped_column(Text, nullable=False)
    storage_url: Mapped[str] = mapped_column(Text, nullable=False)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calibration_scale_mm_per_px: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    quality_check_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    client_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256_hash: Mapped[str | None] = mapped_column(Text, nullable=True)  # Section 65B/BSA 63 digital integrity

    __table_args__ = (
        CheckConstraint(
            "image_role IN ('front_pdp','back_panel','side_panel','sticker','ecommerce_listing')", name="ck_images_role"
        ),
        Index("idx_images_inspection", "inspection_id"),
        Index("idx_images_client_id", "client_id"),
        Index("idx_images_sha256", "sha256_hash"),
    )

    inspection: Mapped["Inspection"] = relationship(back_populates="images")


# ---------------------------------------------------------------------------
# extracted_fields
# ---------------------------------------------------------------------------
class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False
    )
    source_image_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("inspection_images.id"), nullable=False)
    field_type: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric, nullable=False)
    bounding_box: Mapped[dict] = mapped_column(JSON, nullable=False)  # {x, y, w, h}
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by_officer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    officer_override_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("verdict IN ('pass','fail','needs_review','not_applicable')", name="ck_fields_verdict"),
        Index("idx_fields_inspection", "inspection_id"),
        Index("idx_fields_verdict", "verdict"),
    )

    inspection: Mapped["Inspection"] = relationship(back_populates="fields")


# ---------------------------------------------------------------------------
# violations
# ---------------------------------------------------------------------------
class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False
    )
    extracted_field_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("extracted_fields.id"), nullable=True)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    rule_pack_version: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

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

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False
    )
    format: Mapped[str] = mapped_column(Text, nullable=False)
    storage_url: Mapped[str] = mapped_column(Text, nullable=False)
    generated_by: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

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

    version: Mapped[str] = mapped_column(Text, primary_key=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# audit_logs  (append-only â€” no UPDATE or DELETE ever)
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    before_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(Text, nullable=True)  # Cryptographic chaining
    entry_hash: Mapped[str | None] = mapped_column(Text, nullable=True)  # Tamper-evident hash
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_actor", "actor_user_id"),
        Index("idx_audit_entry_hash", "entry_hash"),
    )


# ---------------------------------------------------------------------------
# Evidentiary Immutability & Tamper-Evident Hash Chain Enforcement (E4-04)
# ---------------------------------------------------------------------------
@event.listens_for(AuditLog, "before_insert")
def compute_audit_log_hash(mapper, connection, target: AuditLog):
    """Automatically compute tamper-evident SHA-256 hash for each audit record."""
    if not target.entry_hash:
        before_str = json.dumps(target.before_value, sort_keys=True) if target.before_value else ""
        after_str = json.dumps(target.after_value, sort_keys=True) if target.after_value else ""
        payload = (
            f"{target.prev_hash or 'GENESIS'}:"
            f"{target.actor_user_id}:"
            f"{target.action}:"
            f"{target.entity_type}:"
            f"{target.entity_id}:"
            f"{before_str}:"
            f"{after_str}"
        )
        target.entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()


@event.listens_for(AuditLog, "before_update")
def prevent_audit_log_update(mapper, connection, target: AuditLog):
    """Statutory non-repudiation: reject any attempt to mutate audit records."""
    raise PermissionError("AuditLog records are append-only and legally immutable. UPDATE is strictly forbidden.")


@event.listens_for(AuditLog, "before_delete")
def prevent_audit_log_delete(mapper, connection, target: AuditLog):
    """Statutory non-repudiation: reject any attempt to purge audit records."""
    raise PermissionError("AuditLog records are append-only and legally immutable. DELETE is strictly forbidden.")

