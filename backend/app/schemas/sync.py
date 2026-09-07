import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.inspection import ImageRoleType


class OfflineSyncImageItem(BaseModel):
    client_id: str = Field(description="Client-generated unique ID for this image")
    image_role: ImageRoleType
    data_url: str = Field(description="Base64 encoded Data URL for image content")
    quality_check_passed: bool = Field(default=True)
    width_px: int | None = None
    height_px: int | None = None
    captured_at: datetime | None = None


class OfflineSyncInspectionItem(BaseModel):
    client_id: str = Field(description="Client-generated unique ID for this inspection")
    commodity_category: str | None = Field(default="general")
    captured_offline: bool = Field(default=True)
    created_at: datetime | None = None
    is_self_check: bool = Field(default=False)
    region: str | None = None
    images: list[OfflineSyncImageItem] = Field(default_factory=list)


class OfflineConflictDetail(BaseModel):
    code: Literal[
        "INSPECTION_FINALISED",
        "INSPECTION_FINALIZED",
        "CONCURRENT_MODIFICATION",
        "DUPLICATE_CLIENT_ID",
        "IMAGE_ALREADY_EXISTS",
    ]
    message: str
    inspection_id: str | None = None
    server_status: str | None = None
    suggested_resolution: Literal["server_authoritative", "retry", "abort", "skip"] = "server_authoritative"


class OfflineSyncResult(BaseModel):
    success: bool
    client_id: str
    inspection_id: uuid.UUID | None = None
    status: str
    images_synced: int = 0
    images_skipped: int = 0
    conflict: OfflineConflictDetail | None = None
    error: str | None = None


class BatchOfflineSyncRequest(BaseModel):
    inspections: list[OfflineSyncInspectionItem]


class BatchOfflineSyncResponse(BaseModel):
    total: int
    successful: int
    conflicted: int
    failed: int
    results: list[OfflineSyncResult]
