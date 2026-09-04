"""Pydantic schemas for the eMaap (National Legal Metrology Portal) integration adapter (E4-05)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EMaapRegistrationLookupRequest(BaseModel):
    registration_number: str = Field(
        ...,
        description="LMPC Manufacturer/Packer/Importer registration number (e.g. REG-LMPC-2023-DL-0012).",
        min_length=3,
        max_length=64,
    )
    company_name: str | None = Field(
        default=None,
        description="Optional company name to cross-validate against registration record.",
    )


class EMaapRegistrationResponse(BaseModel):
    is_registered: bool
    registration_number: str
    status: Literal["ACTIVE", "EXPIRED", "SUSPENDED", "NOT_FOUND"]
    entity_name: str | None = None
    entity_type: str | None = None
    registered_address: str | None = None
    valid_until: str | None = None
    authorized_commodity_categories: list[str] = []
    is_sandbox: bool = False
    verified_at: datetime


class EMaapDocketSubmissionRequest(BaseModel):
    officer_notes: str | None = Field(
        default=None,
        description="Field officer observations or special compounding recommendation.",
    )
    priority: Literal["ROUTINE", "URGENT", "SPECIAL_DRIVE"] = Field(
        default="ROUTINE",
        description="Priority classification for eMaap judicial processing.",
    )


class EMaapDocketSubmissionResponse(BaseModel):
    docket_id: str
    inspection_id: uuid.UUID
    status: Literal["ACKNOWLEDGED", "SUBMITTED", "REJECTED"]
    submitted_at: datetime
    evidence_chain_hash: str
    violations_count: int
    photographs_count: int
    portal_tracking_url: str
    is_sandbox: bool = False
    message: str


class EMaapAdapterStatusResponse(BaseModel):
    is_enabled: bool
    is_sandbox: bool
    api_endpoint: str | None
    version: str = "1.0.0"
    supported_operations: list[str] = [
        "registration_verification",
        "enforcement_docket_submission",
    ]
