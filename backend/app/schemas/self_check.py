import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.inspection import ExtractedFieldRead, InspectionImageRead, ViolationRead


class SelfCheckCreate(BaseModel):
    commodity_category: str = Field(default="general", description="Commodity category for rule pack applicability")
    brand_name: str | None = Field(default=None, description="Brand or trade name")
    product_name: str | None = Field(default=None, description="Product description or name")
    batch_or_lot_number: str | None = Field(default=None, description="Internal manufacturing lot or batch")
    pdp_area_sq_cm: float | None = Field(default=None, description="Principal Display Panel area in cm2")
    rule_pack_version: str | None = Field(default=None, description="Target rule pack version")


class SelfCheckRemediationItem(BaseModel):
    rule_id: str
    citation: str | None = None
    severity: str
    issue: str
    remedial_action: str
    field_name: str | None = None


class SelfCheckScorecardRead(BaseModel):
    inspection_id: uuid.UUID
    brand_name: str | None = None
    product_name: str | None = None
    commodity_category: str
    status: str
    overall_readiness: Literal["MARKET_READY", "ACTION_REQUIRED", "CRITICAL_DEFICIENCIES"]
    total_declarations_checked: int
    compliant_count: int
    violation_count: int
    readiness_percentage: float
    remediations: list[SelfCheckRemediationItem]
    created_at: datetime
    disclaimer: str = (
        "THIS IS A PRE-DISTRIBUTION SELF-ASSESSMENT COMPLIANCE AUDIT PERFORMED BY/FOR THE PACKER/MANUFACTURER. "
        "IT DOES NOT CONSTITUTE A FORMAL REGULATORY INSPECTION OR STATUTORY IMMUNITY UNDER THE LEGAL METROLOGY ACT, 2009."
    )

    model_config = ConfigDict(from_attributes=True)


class SelfCheckInspectionRead(BaseModel):
    id: uuid.UUID
    officer_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    commodity_category: str | None = None
    rule_pack_version: str
    status: str
    is_self_check: bool = True
    created_at: datetime
    updated_at: datetime
    images: list[InspectionImageRead] = []
    fields: list[ExtractedFieldRead] = []
    violations: list[ViolationRead] = []

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def sync_user_and_officer_id(self) -> "SelfCheckInspectionRead":
        if self.user_id is None and self.officer_id is not None:
            self.user_id = self.officer_id
        elif self.officer_id is None and self.user_id is not None:
            self.officer_id = self.user_id
        return self


class SelfCheckSummaryStats(BaseModel):
    total_self_checks: int
    market_ready_count: int
    action_required_count: int
    first_pass_rate: float
    common_deficiencies: list[dict[str, Any]]
