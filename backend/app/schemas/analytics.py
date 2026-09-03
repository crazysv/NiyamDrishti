import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnalyticsSummaryResponse(BaseModel):
    total_inspections: int
    completed_inspections: int
    needs_review_inspections: int
    draft_inspections: int
    compliant_inspections: int
    violation_inspections: int
    overall_compliance_rate: float
    total_violations: int
    critical_violations: int
    major_violations: int
    moderate_violations: int
    total_audit_overrides: int
    active_officers_count: int


class ComplianceTrendPoint(BaseModel):
    date: str
    total_inspections: int
    compliant_count: int
    violation_count: int
    compliance_rate: float


class ComplianceTrendsResponse(BaseModel):
    points: list[ComplianceTrendPoint]
    period_start: str | None = None
    period_end: str | None = None


class RuleViolationHotspot(BaseModel):
    rule_id: str
    citation: str | None = None
    description: str
    count: int
    severity: str


class CategoryViolationHotspot(BaseModel):
    commodity_category: str
    total_inspections: int
    violations_count: int
    compliance_rate: float


class RegionViolationHotspot(BaseModel):
    region: str
    total_inspections: int
    violations_count: int
    compliance_rate: float


class ViolationHotspotsResponse(BaseModel):
    by_rule: list[RuleViolationHotspot]
    by_category: list[CategoryViolationHotspot]
    by_region: list[RegionViolationHotspot]


class OfficerThroughputItem(BaseModel):
    officer_id: uuid.UUID
    officer_name: str
    email: str
    region: str | None = None
    total_inspections: int
    completed_inspections: int
    needs_review_inspections: int
    human_overrides_count: int
    last_inspection_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class OfficerThroughputResponse(BaseModel):
    officers: list[OfficerThroughputItem]
    total_active_officers: int
