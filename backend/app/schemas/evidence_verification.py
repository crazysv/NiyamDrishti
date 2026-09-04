"""Pydantic schemas for Evidence Chain Verification and Section 65B/BSA 63 Electronic Evidence Certificate."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ImageEvidenceRecord(BaseModel):
    image_id: uuid.UUID
    image_role: str
    sha256_hash: str | None
    captured_at: datetime
    uploaded_at: datetime
    width_px: int | None = None
    height_px: int | None = None
    calibration_scale_mm_per_px: float | None = None
    file_integrity: Literal["verified", "hash_mismatch", "file_missing", "unhashed"]
    storage_url: str


class AuditLogChainItem(BaseModel):
    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: str
    created_at: datetime
    prev_hash: str | None
    entry_hash: str | None
    is_valid_hash: bool


class EvidenceVerificationResult(BaseModel):
    inspection_id: uuid.UUID
    overall_status: Literal["VERIFIED", "COMPROMISED", "INCOMPLETE"]
    is_tamper_free: bool
    evidence_chain_hash: str
    rule_pack_version: str
    images_count: int
    images_verified: int
    images_compromised: int
    fields_count: int
    violations_count: int
    audit_events_count: int
    audit_chain_intact: bool
    image_records: list[ImageEvidenceRecord]
    audit_chain: list[AuditLogChainItem]
    verified_at: datetime
    verification_notes: list[str]


class Section65BCertificate(BaseModel):
    certificate_id: str
    title: str = "CERTIFICATE OF ELECTRONIC EVIDENCE (SECTION 63 BSA 2023 / SECTION 65B EVIDENCE ACT 1872)"
    inspection_id: str
    generated_at: datetime
    officer_name: str
    officer_email: str
    officer_role: str
    officer_region: str | None
    rule_pack_version: str
    commodity_category: str | None
    evidence_chain_hash: str
    audit_chain_intact: bool
    photographic_schedule: list[dict[str, Any]]
    chain_of_custody_log: list[dict[str, Any]]
    system_environment: dict[str, str]
    statutory_attestation: str
