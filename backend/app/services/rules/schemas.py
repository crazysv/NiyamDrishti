import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RuleType = Literal[
    "field_required",
    "font_height_by_pdp_area",
    "font_height_blown_embossed",
    "legibility_contrast",
    "format_match",
    "date_validity",
]
SeverityType = Literal["minor", "major", "critical"]
VerdictType = Literal["pass", "fail", "needs_review", "not_applicable"]


class RuleDefinition(BaseModel):
    """Definition of an individual Legal Metrology compliance rule."""

    rule_id: str = Field(..., description="Unique rule identifier within the pack, e.g. 'declaration-present-mrp'")
    applies_to: list[str] = Field(
        default=["all"],
        description="Target commodity categories (e.g. ['all'] or ['pan_masala', 'packaged_food'])",
    )
    type: RuleType = Field(..., description="Rule evaluation type determining engine dispatch")
    field: str | None = Field(default=None, description="Target extracted field type (e.g. 'mrp', 'net_quantity')")
    citation: str | None = Field(
        default=None,
        description="Legal citation reference (e.g. 'Rule 6 — [VERIFY exact sub-clause]'). Must carry [VERIFY] if unverified.",
    )
    severity: SeverityType = Field(default="major", description="Violation severity level")
    thresholds_mm: dict[str, float] | None = Field(
        default=None,
        description="Bracket thresholds for font height by PDP area (e.g. {'50': 1.0, '100': 1.5, ...})",
    )
    requires_calibration: bool = Field(
        default=False,
        description="If True, requires optical calibration; uncalibrated images will be flagged as needs_review",
    )
    note: str | None = Field(default=None, description="Regulatory note or amendment justification")

    @model_validator(mode="after")
    def validate_rule_type_requirements(self) -> "RuleDefinition":
        if self.type == "field_required" and not self.field:
            raise ValueError(f"Rule '{self.rule_id}' of type 'field_required' must specify 'field'")
        if self.type in ("font_height_by_pdp_area", "font_height_blown_embossed") and not self.thresholds_mm:
            raise ValueError(f"Rule '{self.rule_id}' of type '{self.type}' must specify 'thresholds_mm'")
        return self


class RulePackSchema(BaseModel):
    """Versioned Rule Pack JSON Schema conforming to 06_SCHEMA.md §3."""

    rule_pack_version: str = Field(..., description="Rule pack version, e.g. '2026.02.01'")
    effective_from: date = Field(..., description="Date from which the rule pack takes legal effect")
    effective_to: date | None = Field(
        default=None,
        description="Optional expiration date if superseded by a newer amendment",
    )
    source_citation: str | None = Field(
        default=None,
        description="Official gazette or statutory order reference",
    )
    rules: list[RuleDefinition] = Field(..., min_length=1, description="List of rule definitions")

    model_config = ConfigDict(extra="ignore")


class RuleEvaluationResult(BaseModel):
    """Result of evaluating a single rule against an inspection's extracted declarations."""

    rule_id: str
    verdict: VerdictType
    field_id: uuid.UUID | None = None
    field_type: str | None = None
    description: str
    citation: str | None = None
    severity: SeverityType
    bounding_box: dict | None = None
    is_calibrated: bool = True
    warning: str | None = None


class EvaluationSummary(BaseModel):
    """Aggregated evaluation verdict and violations for an inspection."""

    overall_status: VerdictType
    rule_pack_version: str
    results: list[RuleEvaluationResult]
    violations: list[dict]
