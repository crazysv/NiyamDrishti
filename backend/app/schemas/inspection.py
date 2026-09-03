import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ImageRoleType = Literal["front_pdp", "back_panel", "side_panel", "sticker", "ecommerce_listing"]
InspectionStatusType = Literal["draft", "processing", "needs_review", "completed", "sync_pending"]


class InspectionCreate(BaseModel):
    commodity_category: str | None = Field(default="general")
    captured_offline: bool = Field(default=False)
    created_at: datetime | None = None
    is_self_check: bool = Field(default=False)


class InspectionImageCreate(BaseModel):
    image_role: ImageRoleType
    data_url: str | None = None
    captured_at: datetime | None = None
    quality_check_passed: bool = True
    width_px: int | None = None
    height_px: int | None = None


class InspectionImageRead(BaseModel):
    id: uuid.UUID
    inspection_id: uuid.UUID
    image_role: str
    storage_url: str
    width_px: int | None = None
    height_px: int | None = None
    calibration_scale_mm_per_px: float | None = None
    quality_check_passed: bool
    captured_at: datetime
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractedFieldRead(BaseModel):
    id: uuid.UUID
    inspection_id: uuid.UUID
    source_image_id: uuid.UUID
    field_type: str
    raw_text: str | None = None
    parsed_value: str | None = None
    confidence: float
    bounding_box: dict
    verdict: str
    reviewed_by_officer: bool
    officer_override_value: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ViolationRead(BaseModel):
    id: uuid.UUID
    inspection_id: uuid.UUID
    extracted_field_id: uuid.UUID | None = None
    rule_id: str
    rule_pack_version: str
    description: str
    citation: str | None = None
    severity: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InspectionRead(BaseModel):
    id: uuid.UUID
    officer_id: uuid.UUID
    status: str
    commodity_category: str | None = None
    rule_pack_version: str
    is_self_check: bool
    region: str | None = None
    captured_offline: bool
    created_at: datetime
    updated_at: datetime
    synced_at: datetime | None = None
    images: list[InspectionImageRead] = []
    fields: list[ExtractedFieldRead] = []
    violations: list[ViolationRead] = []

    model_config = ConfigDict(from_attributes=True)


class InspectionSummaryRead(BaseModel):
    id: uuid.UUID
    officer_id: uuid.UUID
    officer_name: str | None = None
    status: str
    commodity_category: str | None = None
    rule_pack_version: str
    region: str | None = None
    captured_offline: bool = False
    created_at: datetime
    updated_at: datetime
    violations_count: int = 0
    fields_count: int = 0
    images_count: int = 0
    thumbnail_url: str | None = None
    overall_verdict: str = "compliant"

    model_config = ConfigDict(from_attributes=True)


class InspectionListResponse(BaseModel):
    items: list[InspectionSummaryRead]
    total: int
    skip: int
    limit: int


class EvidenceItemRead(BaseModel):
    item_id: str  # E01, E02, etc.
    field_id: uuid.UUID
    field_type: str
    field_label: str
    raw_text: str | None = None
    parsed_value: str | None = None
    confidence: float
    verdict: str
    bounding_box: dict
    source_image_id: uuid.UUID
    source_image_url: str
    is_calibrated: bool = False
    measured_dimension: dict | None = None
    violations: list[ViolationRead] = []


class InspectionEvidenceRead(BaseModel):
    inspection_id: uuid.UUID
    product_name: str
    commodity_category: str
    overall_status: str
    rule_pack_version: str
    officer_id: uuid.UUID
    officer_name: str | None = None
    primary_image_url: str | None = None
    primary_image_dimensions: dict | None = None
    items: list[EvidenceItemRead] = []
    stats: dict


FieldReviewAction = Literal["confirm", "correct", "mark_not_applicable"]


class FieldReviewUpdate(BaseModel):
    action: FieldReviewAction
    officer_override_value: str | None = Field(
        default=None,
        description="Corrected/normalized value provided by officer. Required when action is 'correct'.",
    )
    review_notes: str | None = Field(
        default=None,
        description="Optional notes explaining officer's review decision.",
    )


class FieldReviewResponse(BaseModel):
    field: ExtractedFieldRead
    inspection_status: str
    violations_count: int
    audit_log_id: uuid.UUID
    message: str


class AuditLogRead(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID
    action: str
    entity_type: str
    entity_id: str
    before_value: dict | None = None
    after_value: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewQueueItemRead(BaseModel):
    field_id: uuid.UUID
    inspection_id: uuid.UUID
    field_type: str
    field_label: str
    raw_text: str | None = None
    parsed_value: str | None = None
    confidence: float
    verdict: str
    bounding_box: dict
    source_image_id: uuid.UUID
    source_image_url: str
    flag_reason: str
    reviewed_by_officer: bool
    officer_override_value: str | None = None
    violations: list[ViolationRead] = []


class InspectionReviewQueueResponse(BaseModel):
    inspection_id: uuid.UUID
    overall_status: str
    total_fields: int
    pending_review_count: int
    completed_review_count: int
    items: list[ReviewQueueItemRead]


class FieldBatchReviewItem(BaseModel):
    field_id: uuid.UUID
    action: Literal["confirm", "override", "mark_not_applicable"]
    officer_override_value: str | None = None
    officer_notes: str | None = None


class BatchFieldReviewRequest(BaseModel):
    items: list[FieldBatchReviewItem]


class BatchFieldReviewResponse(BaseModel):
    inspection_id: uuid.UUID
    inspection_status: str
    reviewed_count: int
    violations_count: int
    updated_fields: list[ExtractedFieldRead]
    audit_log_ids: list[uuid.UUID]
    message: str


ReportFormatType = Literal["pdf", "editable"]


class ReportGenerateRequest(BaseModel):
    format: ReportFormatType = "pdf"


class ReportRead(BaseModel):
    id: uuid.UUID
    inspection_id: uuid.UUID
    format: str
    storage_url: str
    download_url: str
    generated_by: uuid.UUID
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)
