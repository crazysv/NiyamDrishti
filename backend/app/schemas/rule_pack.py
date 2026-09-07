import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RulePackCreate(BaseModel):
    version: str = Field(..., description="Semantic or date version string, e.g. '2026.02.01'")
    effective_from: datetime = Field(..., description="Timestamp or date when rules take effect")
    effective_to: datetime | None = Field(default=None, description="Optional sunset date")
    source_citation: str | None = Field(default=None, description="Gazette or legal reference citation")
    rules_json: dict = Field(..., description="Full rule pack JSON payload conforming to RulePackSchema")


class RulePackSummaryRead(BaseModel):
    version: str
    effective_from: datetime
    effective_to: datetime | None = None
    source_citation: str | None = None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    rule_count: int

    model_config = ConfigDict(from_attributes=True)


class RulePackDetailRead(BaseModel):
    version: str
    effective_from: datetime
    effective_to: datetime | None = None
    source_citation: str | None = None
    rules_json: dict
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
