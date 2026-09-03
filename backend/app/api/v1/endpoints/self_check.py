"""
Manufacturer / Packer Self-Check Mode Endpoints (E3-06, 01_PRD.md NG4, 06_SCHEMA.md).
Provides a structurally separate data path for brand manufacturers, FMCG packers,
and packaging artwork designers to verify compliance against Legal Metrology (Packaged Commodities)
Rules, 2011 prior to commercial distribution.

Key Architectural Guarantees:
1. All created inspections have is_self_check = True.
2. Self-checks are strictly isolated and NEVER joined into regulatory enforcement dashboards,
   officer throughput metrics, or penalty notices.
3. Provides constructive packaging remediation advisory instead of punitive citations.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.models.base import ExtractedField, Inspection, InspectionImage, User, Violation
from app.schemas.self_check import (
    SelfCheckCreate,
    SelfCheckInspectionRead,
    SelfCheckRemediationItem,
    SelfCheckScorecardRead,
    SelfCheckSummaryStats,
)

router = APIRouter()


def _generate_remedial_action(v: Violation) -> str:
    """Generates constructive packaging design guidance for a detected violation."""
    rule_lower = (v.rule_id or "").lower()
    desc_lower = (v.description or "").lower()

    if "mrp" in rule_lower or "mrp" in desc_lower or "price" in desc_lower:
        return (
            "Print MRP clearly as 'Maximum or Max. Retail Price Rs./₹ ... (inclusive of all taxes)' "
            "per Rule 6(1)(e). Do not use non-standard acronyms or omit the tax-inclusive clause."
        )
    if "net" in rule_lower or "quantity" in desc_lower or "weight" in desc_lower:
        return (
            "Ensure net quantity declaration uses standard SI units with mandatory spaces (e.g., '100 g', '1 kg', '500 ml'). "
            "Check Schedule II for minimum numeral font height based on your package display area."
        )
    if "date" in rule_lower or "mfg" in desc_lower or "expiry" in desc_lower or "month" in desc_lower:
        return (
            "Indicate month and year of manufacture/packaging in standard format ('MM/YYYY' or 'Month YYYY') "
            "per Rule 6(1)(d). Ensure font height is distinct and legible."
        )
    if "consumer" in rule_lower or "care" in desc_lower or "contact" in desc_lower:
        return (
            "Include complete consumer care contact details: designated officer/department name, "
            "valid phone number, email address, and complete physical postal address per Rule 6(1)(g)."
        )
    if "origin" in rule_lower or "country" in desc_lower or "import" in desc_lower:
        return (
            "For imported commodities, mention the Country of Origin explicitly on the principal display panel "
            "along with the name and complete address of the importer per Rule 6(1)(f)."
        )
    return (
        f"Review packaging artwork against statutory provision {v.citation or v.rule_id} "
        "and correct label declarations prior to commercial printing run."
    )


@router.post("/inspections", response_model=SelfCheckInspectionRead, status_code=status.HTTP_201_CREATED)
async def create_self_check(
    payload: SelfCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SelfCheckInspectionRead:
    """
    Initiates a new manufacturer/packer pre-distribution self-assessment.
    Guaranteed to flag is_self_check = True so it is isolated from enforcement queues.
    """
    rule_pack_ver = payload.rule_pack_version or settings.ACTIVE_RULE_PACK_VERSION

    inspection = Inspection(
        officer_id=current_user.id,
        commodity_category=payload.commodity_category,
        rule_pack_version=rule_pack_ver,
        status="draft",
        is_self_check=True,  # Structurally separate data path
        captured_offline=False,
        region=current_user.region or "Pre-Distribution Audit",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(inspection)
    await db.commit()

    # Re-fetch with eager loads
    stmt = (
        select(Inspection)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
        )
        .where(Inspection.id == inspection.id)
    )
    res = await db.execute(stmt)
    created = res.scalar_one()

    return SelfCheckInspectionRead(
        id=created.id,
        user_id=created.officer_id,
        commodity_category=created.commodity_category,
        rule_pack_version=created.rule_pack_version,
        status=created.status,
        is_self_check=created.is_self_check,
        created_at=created.created_at,
        updated_at=created.updated_at,
        images=[],
        fields=[],
        violations=[],
    )


@router.get("/inspections", response_model=list[SelfCheckInspectionRead])
async def list_self_checks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[SelfCheckInspectionRead]:
    """
    Lists self-check audits conducted by the authenticated manufacturer/packer.
    """
    stmt = (
        select(Inspection)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
        )
        .where(Inspection.is_self_check == True)
    )

    # Scoped to current manufacturer/user unless supervisor/admin
    if current_user.role not in ("admin", "supervisor"):
        stmt = stmt.where(Inspection.officer_id == current_user.id)

    stmt = stmt.order_by(Inspection.created_at.desc()).offset(skip).limit(limit)
    res = await db.execute(stmt)
    records = res.scalars().all()

    return [
        SelfCheckInspectionRead(
            id=rec.id,
            user_id=rec.officer_id,
            commodity_category=rec.commodity_category,
            rule_pack_version=rec.rule_pack_version,
            status=rec.status,
            is_self_check=rec.is_self_check,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
            images=rec.images,
            fields=rec.fields,
            violations=rec.violations,
        )
        for rec in records
    ]


@router.get("/inspections/{inspection_id}", response_model=SelfCheckInspectionRead)
async def get_self_check(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SelfCheckInspectionRead:
    """
    Retrieves details of a specific self-check audit.
    """
    stmt = (
        select(Inspection)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
        )
        .where(Inspection.id == inspection_id, Inspection.is_self_check == True)
    )
    res = await db.execute(stmt)
    rec = res.scalar_one_or_none()

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Self-check inspection not found",
        )

    if current_user.role not in ("admin", "supervisor") and rec.officer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this self-check record",
        )

    return SelfCheckInspectionRead(
        id=rec.id,
        user_id=rec.officer_id,
        commodity_category=rec.commodity_category,
        rule_pack_version=rec.rule_pack_version,
        status=rec.status,
        is_self_check=rec.is_self_check,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        images=rec.images,
        fields=rec.fields,
        violations=rec.violations,
    )


@router.get("/inspections/{inspection_id}/scorecard", response_model=SelfCheckScorecardRead)
async def get_self_check_scorecard(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SelfCheckScorecardRead:
    """
    Generates a constructive pre-distribution compliance scorecard with
    detailed remediation guidance for packaging artwork and labeling teams.
    """
    stmt = (
        select(Inspection)
        .options(
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
        )
        .where(Inspection.id == inspection_id, Inspection.is_self_check == True)
    )
    res = await db.execute(stmt)
    inspection = res.scalar_one_or_none()

    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Self-check inspection not found",
        )

    if current_user.role not in ("admin", "supervisor") and inspection.officer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this self-check scorecard",
        )

    total_fields = len(inspection.fields or [])
    violation_count = len(inspection.violations or [])
    compliant_count = max(0, total_fields - violation_count)

    # Readiness status
    critical_count = sum(1 for v in (inspection.violations or []) if v.severity == "critical")
    if critical_count > 0:
        readiness = "CRITICAL_DEFICIENCIES"
    elif violation_count > 0:
        readiness = "ACTION_REQUIRED"
    else:
        readiness = "MARKET_READY"

    # Readiness percentage
    if total_fields > 0:
        readiness_pct = round((compliant_count / total_fields) * 100.0, 1)
    else:
        readiness_pct = 100.0 if violation_count == 0 else 0.0

    remediations: list[SelfCheckRemediationItem] = []
    for v in (inspection.violations or []):
        field_name = None
        if v.extracted_field_id:
            for f in (inspection.fields or []):
                if f.id == v.extracted_field_id:
                    field_name = f.field_type
                    break

        remediations.append(
            SelfCheckRemediationItem(
                rule_id=v.rule_id,
                citation=v.citation,
                severity=v.severity,
                issue=v.description,
                remedial_action=_generate_remedial_action(v),
                field_name=field_name,
            )
        )

    return SelfCheckScorecardRead(
        inspection_id=inspection.id,
        commodity_category=inspection.commodity_category or "general",
        status=inspection.status,
        overall_readiness=readiness,
        total_declarations_checked=total_fields,
        compliant_count=compliant_count,
        violation_count=violation_count,
        readiness_percentage=readiness_pct,
        remediations=remediations,
        created_at=inspection.created_at,
    )


@router.get("/summary", response_model=SelfCheckSummaryStats)
async def get_self_check_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SelfCheckSummaryStats:
    """
    Aggregates self-check metrics for the current manufacturer/packer account.
    """
    stmt = (
        select(Inspection)
        .options(selectinload(Inspection.violations))
        .where(Inspection.is_self_check == True)
    )
    if current_user.role not in ("admin", "supervisor"):
        stmt = stmt.where(Inspection.officer_id == current_user.id)

    res = await db.execute(stmt)
    records = res.scalars().all()

    total = len(records)
    market_ready = 0
    action_required = 0
    deficiency_tally: dict[str, dict] = {}

    for rec in records:
        v_count = len(rec.violations or [])
        if v_count == 0:
            market_ready += 1
        else:
            action_required += 1

        for v in (rec.violations or []):
            rid = v.rule_id
            if rid not in deficiency_tally:
                deficiency_tally[rid] = {
                    "rule_id": rid,
                    "citation": v.citation,
                    "description": v.description,
                    "count": 0,
                }
            deficiency_tally[rid]["count"] += 1

    first_pass_rate = round((market_ready / total * 100.0), 1) if total > 0 else 100.0

    sorted_deficiencies = sorted(deficiency_tally.values(), key=lambda x: x["count"], reverse=True)[:5]

    return SelfCheckSummaryStats(
        total_self_checks=total,
        market_ready_count=market_ready,
        action_required_count=action_required,
        first_pass_rate=first_pass_rate,
        common_deficiencies=sorted_deficiencies,
    )
