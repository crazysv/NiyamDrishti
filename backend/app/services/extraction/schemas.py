from typing import Any

from pydantic import BaseModel, Field


class ExtractedDeclaration(BaseModel):
    """
    Structured representation of a Legal Metrology declaration extracted from label text.
    Matches extracted_fields schema from 06_SCHEMA.md.
    """

    field_type: str = Field(
        ...,
        description="Type: mrp, net_quantity, manufacturer_address, mfg_date, consumer_care, country_of_origin, commodity_name",
    )
    raw_text: str = Field(..., description="Unmodified raw text as seen on the label")
    parsed_value: str = Field(..., description="Normalized/structured value formatted as string or JSON string")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score (0.0 - 1.0)")
    bounding_box: dict[str, Any] = Field(
        ..., description="Traceable bounding box in original image coordinates {x, y, w, h}"
    )
    source_image_id: str = Field(..., description="UUID string of the source inspection_image")
    verdict: str = Field(
        default="needs_review",
        description="'pass', 'fail', 'needs_review', or 'not_applicable'",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Auxiliary parsed attributes")
