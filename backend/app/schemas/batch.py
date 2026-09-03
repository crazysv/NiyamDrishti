"""
Pydantic schemas for Batch / Warehouse Scanning Mode (E3-05, MASTER_CONTENT.md §10.13).
Supports rapid multi-SKU intake, live tallying, and warehouse audit manifest generation.
"""

from datetime import datetime
from typing import Any, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class BatchSessionCreate(BaseModel):
    session_name: str = Field(..., min_length=2, max_length=150, description="Warehouse audit or raid session name")
    premises_name: Optional[str] = Field(None, max_length=150, description="Name of the warehouse, dark store, or distributor")
    premises_address: Optional[str] = Field(None, max_length=250, description="Physical location of the premises")
    region: Optional[str] = Field(None, max_length=100, description="Enforcement region / zone")
    notes: Optional[str] = Field(None, description="Initial raid or inspection notes")


class BatchSessionUpdate(BaseModel):
    session_name: Optional[str] = None
    premises_name: Optional[str] = None
    premises_address: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = Field(None, description="'active', 'completed', 'archived'")


class BatchSKUItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inspection_id: uuid.UUID
    status: str
    commodity_category: Optional[str]
    created_at: datetime
    violations_count: int
    is_compliant: bool
    mrp: Optional[str] = None
    net_quantity: Optional[str] = None
    commodity_name: Optional[str] = None


class BatchSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    officer_id: uuid.UUID
    session_name: str
    premises_name: Optional[str]
    premises_address: Optional[str]
    region: Optional[str]
    status: str
    notes: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    total_skus_scanned: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    pending_count: int = 0
    compliance_rate_pct: float = 0.0


class BatchSessionDetail(BatchSessionRead):
    items: list[BatchSKUItem] = []


class BatchManifestRead(BaseModel):
    session_id: uuid.UUID
    session_name: str
    officer_id: uuid.UUID
    premises_name: Optional[str]
    premises_address: Optional[str]
    region: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    total_skus: int
    compliant_skus: int
    non_compliant_skus: int
    compliance_rate_pct: float
    total_violations: int
    violations_by_rule: dict[str, int]
    items: list[dict[str, Any]]
