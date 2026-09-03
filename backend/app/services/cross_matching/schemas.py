import uuid
from typing import Any, Literal
from pydantic import BaseModel, Field

DiscrepancySeverity = Literal["minor", "major", "critical"]


class FieldOccurrence(BaseModel):
    """Occurrence of an extracted field in a specific inspection image."""

    field_id: uuid.UUID | None = None
    source_image_id: uuid.UUID
    image_role: str = Field(..., description="Role: front_pdp, back_panel, side_panel, sticker, ecommerce_listing")
    raw_text: str
    parsed_value: Any
    confidence: float
    bounding_box: dict[str, Any] | None = None


class CrossMatchDiscrepancy(BaseModel):
    """Detailed discrepancy found between multiple images of the same package."""

    field_type: str = Field(..., description="Target field: mrp, net_quantity, mfg_date, country_of_origin")
    discrepancy_type: str = Field(
        ...,
        description="Type: mrp_altered_sticker, net_quantity_mismatch, date_mismatch, country_mismatch",
    )
    severity: DiscrepancySeverity = "major"
    rule_id: str
    citation: str
    description: str
    source_image_ids: list[uuid.UUID] = Field(default_factory=list)
    occurrences: list[FieldOccurrence] = Field(default_factory=list)


class CrossMatchReport(BaseModel):
    """Overall report summarizing cross-image declaration consistency."""

    inspection_id: uuid.UUID
    total_images: int
    total_declarations_compared: int
    is_consistent: bool
    discrepancies: list[CrossMatchDiscrepancy] = Field(default_factory=list)
    consistent_fields: list[str] = Field(default_factory=list)
