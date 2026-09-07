"""
Batch / Warehouse Scanning Mode Endpoints (E3-05, MASTER_CONTENT.md §10.13).
Enables field officers to conduct rapid, multi-SKU inspections during warehouse
audits, dark store raids, and distribution center inspections.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.models.base import BatchSession, Inspection, User
from app.schemas.batch import (
    BatchManifestRead,
    BatchSessionCreate,
    BatchSessionDetail,
    BatchSessionRead,
    BatchSKUItem,
)
from app.schemas.inspection import InspectionCreate, InspectionRead

router = APIRouter()


def _compute_batch_metrics(session: BatchSession) -> dict:
    total = len(session.inspections or [])
    compliant = 0
    non_compliant = 0
    pending = 0

    for insp in session.inspections or []:
        if insp.status == "completed":
            v_count = len(insp.violations or [])
            if v_count == 0:
                compliant += 1
            else:
                non_compliant += 1
        elif insp.status == "needs_review":
            non_compliant += 1
        else:
            pending += 1

    rate = (compliant / total * 100.0) if total > 0 else 0.0

    return {
        "total": total,
        "compliant": compliant,
        "non_compliant": non_compliant,
        "pending": pending,
        "rate": round(rate, 1),
    }


@router.post("", response_model=BatchSessionRead, status_code=status.HTTP_201_CREATED)
async def create_batch_session(
    payload: BatchSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BatchSessionRead:
    """
    Creates a new batch inspection session for warehouse audits or raid operations.
    """
    batch = BatchSession(
        id=uuid.uuid4(),
        officer_id=current_user.id,
        session_name=payload.session_name,
        premises_name=payload.premises_name,
        premises_address=payload.premises_address,
        region=payload.region or current_user.region,
        status="active",
        notes=payload.notes,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    return BatchSessionRead(
        id=batch.id,
        officer_id=batch.officer_id,
        session_name=batch.session_name,
        premises_name=batch.premises_name,
        premises_address=batch.premises_address,
        region=batch.region,
        status=batch.status,
        notes=batch.notes,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
        total_skus_scanned=0,
        compliant_count=0,
        non_compliant_count=0,
        pending_count=0,
        compliance_rate_pct=0.0,
    )


@router.get("", response_model=list[BatchSessionRead])
async def list_batch_sessions(
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[BatchSessionRead]:
    """
    Lists batch warehouse inspection sessions with computed SKU compliance tallies.
    """
    stmt = (
        select(BatchSession)
        .options(
            selectinload(BatchSession.inspections).selectinload(Inspection.violations),
        )
        .order_by(BatchSession.created_at.desc())
    )

    if current_user.role == "officer":
        stmt = stmt.where(BatchSession.officer_id == current_user.id)

    if status_filter:
        stmt = stmt.where(BatchSession.status == status_filter)

    res = await db.execute(stmt)
    batches = res.scalars().all()

    results: list[BatchSessionRead] = []
    for b in batches:
        metrics = _compute_batch_metrics(b)
        results.append(
            BatchSessionRead(
                id=b.id,
                officer_id=b.officer_id,
                session_name=b.session_name,
                premises_name=b.premises_name,
                premises_address=b.premises_address,
                region=b.region,
                status=b.status,
                notes=b.notes,
                created_at=b.created_at,
                completed_at=b.completed_at,
                total_skus_scanned=metrics["total"],
                compliant_count=metrics["compliant"],
                non_compliant_count=metrics["non_compliant"],
                pending_count=metrics["pending"],
                compliance_rate_pct=metrics["rate"],
            )
        )

    return results


@router.get("/{batch_id}", response_model=BatchSessionDetail)
async def get_batch_session_detail(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BatchSessionDetail:
    """
    Retrieves detailed batch session info including all scanned SKU inspection items.
    """
    stmt = (
        select(BatchSession)
        .where(BatchSession.id == batch_id)
        .options(
            selectinload(BatchSession.inspections).selectinload(Inspection.violations),
            selectinload(BatchSession.inspections).selectinload(Inspection.fields),
        )
    )
    res = await db.execute(stmt)
    batch = res.scalar_one_or_none()

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch session {batch_id} not found",
        )

    if batch.officer_id != current_user.id and current_user.role not in ["supervisor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this batch session",
        )

    metrics = _compute_batch_metrics(batch)

    sku_items: list[BatchSKUItem] = []
    for insp in batch.inspections or []:
        v_count = len(insp.violations or [])
        mrp_val = None
        qty_val = None
        name_val = None

        for f in insp.fields or []:
            if f.field_type == "mrp":
                mrp_val = f.parsed_value or f.raw_text
            elif f.field_type == "net_quantity":
                qty_val = f.parsed_value or f.raw_text
            elif f.field_type == "commodity_name":
                name_val = f.parsed_value or f.raw_text

        sku_items.append(
            BatchSKUItem(
                inspection_id=insp.id,
                status=insp.status,
                commodity_category=insp.commodity_category,
                created_at=insp.created_at,
                violations_count=v_count,
                is_compliant=v_count == 0 and insp.status == "completed",
                mrp=mrp_val,
                net_quantity=qty_val,
                commodity_name=name_val,
            )
        )

    return BatchSessionDetail(
        id=batch.id,
        officer_id=batch.officer_id,
        session_name=batch.session_name,
        premises_name=batch.premises_name,
        premises_address=batch.premises_address,
        region=batch.region,
        status=batch.status,
        notes=batch.notes,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
        total_skus_scanned=metrics["total"],
        compliant_count=metrics["compliant"],
        non_compliant_count=metrics["non_compliant"],
        pending_count=metrics["pending"],
        compliance_rate_pct=metrics["rate"],
        items=sku_items,
    )


@router.post("/{batch_id}/inspections", response_model=InspectionRead, status_code=status.HTTP_201_CREATED)
async def create_batch_sku_inspection(
    batch_id: uuid.UUID,
    payload: InspectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Inspection:
    """
    Rapidly creates a new product inspection linked to an active warehouse batch session.
    """
    stmt = select(BatchSession).where(BatchSession.id == batch_id)
    res = await db.execute(stmt)
    batch = res.scalar_one_or_none()

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch session {batch_id} not found",
        )

    if batch.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add SKUs to a batch session with status '{batch.status}'",
        )

    pack_version = payload.rule_pack_version or settings.ACTIVE_RULE_PACK_VERSION or "2026.02.01"

    inspection = Inspection(
        id=uuid.uuid4(),
        officer_id=current_user.id,
        batch_id=batch.id,
        commodity_category=payload.commodity_category,
        rule_pack_version=pack_version,
        is_self_check=payload.is_self_check,
        region=payload.region or batch.region or current_user.region,
        captured_offline=payload.captured_offline,
        status="draft",
    )
    db.add(inspection)
    await db.commit()

    reloaded_stmt = (
        select(Inspection)
        .where(Inspection.id == inspection.id)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
        )
    )
    insp_res = await db.execute(reloaded_stmt)
    return insp_res.scalar_one()


@router.post("/{batch_id}/complete", response_model=BatchSessionRead)
async def complete_batch_session(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BatchSessionRead:
    """
    Marks a warehouse batch session as completed and freezes the audit timeline.
    """
    stmt = (
        select(BatchSession)
        .where(BatchSession.id == batch_id)
        .options(selectinload(BatchSession.inspections).selectinload(Inspection.violations))
    )
    res = await db.execute(stmt)
    batch = res.scalar_one_or_none()

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch session {batch_id} not found",
        )

    if batch.officer_id != current_user.id and current_user.role not in ["supervisor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to close this batch session",
        )

    batch.status = "completed"
    batch.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(batch)

    metrics = _compute_batch_metrics(batch)
    return BatchSessionRead(
        id=batch.id,
        officer_id=batch.officer_id,
        session_name=batch.session_name,
        premises_name=batch.premises_name,
        premises_address=batch.premises_address,
        region=batch.region,
        status=batch.status,
        notes=batch.notes,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
        total_skus_scanned=metrics["total"],
        compliant_count=metrics["compliant"],
        non_compliant_count=metrics["non_compliant"],
        pending_count=metrics["pending"],
        compliance_rate_pct=metrics["rate"],
    )


@router.get("/{batch_id}/manifest", response_model=BatchManifestRead)
async def get_batch_audit_manifest(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BatchManifestRead:
    """
    Generates a consolidated warehouse audit manifest and seizure tally across all SKUs.
    """
    stmt = (
        select(BatchSession)
        .where(BatchSession.id == batch_id)
        .options(
            selectinload(BatchSession.inspections).selectinload(Inspection.violations),
            selectinload(BatchSession.inspections).selectinload(Inspection.fields),
        )
    )
    res = await db.execute(stmt)
    batch = res.scalar_one_or_none()

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch session {batch_id} not found",
        )

    if batch.officer_id != current_user.id and current_user.role not in ["supervisor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this manifest",
        )

    metrics = _compute_batch_metrics(batch)

    violations_by_rule: dict[str, int] = {}
    items: list[dict] = []
    total_violations = 0

    for idx, insp in enumerate(batch.inspections or [], start=1):
        v_list = insp.violations or []
        total_violations += len(v_list)

        for v in v_list:
            violations_by_rule[v.rule_id] = violations_by_rule.get(v.rule_id, 0) + 1

        fields_dict = {f.field_type: f.parsed_value or f.raw_text for f in (insp.fields or [])}

        items.append(
            {
                "item_seq": idx,
                "inspection_id": str(insp.id),
                "status": insp.status,
                "commodity_category": insp.commodity_category,
                "mrp": fields_dict.get("mrp"),
                "net_quantity": fields_dict.get("net_quantity"),
                "manufacturer": fields_dict.get("manufacturer_address") or fields_dict.get("importer_packer"),
                "violations": [
                    {
                        "rule_id": v.rule_id,
                        "severity": v.severity,
                        "description": v.description,
                        "citation": v.citation,
                    }
                    for v in v_list
                ],
                "compliant": len(v_list) == 0 and insp.status == "completed",
            }
        )

    return BatchManifestRead(
        session_id=batch.id,
        session_name=batch.session_name,
        officer_id=batch.officer_id,
        premises_name=batch.premises_name,
        premises_address=batch.premises_address,
        region=batch.region,
        status=batch.status,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
        total_skus=metrics["total"],
        compliant_skus=metrics["compliant"],
        non_compliant_skus=metrics["non_compliant"],
        compliance_rate_pct=metrics["rate"],
        total_violations=total_violations,
        violations_by_rule=violations_by_rule,
        items=items,
    )
