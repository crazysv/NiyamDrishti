from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db, require_supervisor
from app.models.base import AuditLog, Inspection, User, Violation
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    CategoryViolationHotspot,
    ComplianceTrendPoint,
    ComplianceTrendsResponse,
    OfficerThroughputItem,
    OfficerThroughputResponse,
    RegionViolationHotspot,
    RuleViolationHotspot,
    ViolationHotspotsResponse,
)

router = APIRouter()


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AnalyticsSummaryResponse:
    """
    Get top-level compliance and enforcement analytics summary (E2-05 / US-09).
    Supervisors & admins view state-wide metrics; officers view their assigned jurisdiction.
    """
    base_insp_query = select(Inspection)
    if current_user.role == "officer":
        base_insp_query = base_insp_query.where(Inspection.officer_id == current_user.id)

    # 1. Inspection status counts
    status_stmt = select(Inspection.status, func.count(Inspection.id)).group_by(Inspection.status)
    if current_user.role == "officer":
        status_stmt = status_stmt.where(Inspection.officer_id == current_user.id)

    status_res = await db.execute(status_stmt)
    status_counts: dict[str, int] = {str(r[0]): int(r[1]) for r in status_res.all()}

    total_inspections = sum(status_counts.values())
    completed_inspections = status_counts.get("completed", 0)
    needs_review_inspections = status_counts.get("needs_review", 0)
    draft_inspections = status_counts.get("draft", 0)

    # 2. Completed inspections with violations vs compliant
    insp_violation_stmt = (
        select(Inspection.id, func.count(Violation.id))
        .outerjoin(Violation, Inspection.id == Violation.inspection_id)
        .where(Inspection.status == "completed")
        .group_by(Inspection.id)
    )
    if current_user.role == "officer":
        insp_violation_stmt = insp_violation_stmt.where(Inspection.officer_id == current_user.id)

    insp_violation_res = await db.execute(insp_violation_stmt)
    completed_rows = insp_violation_res.all()

    compliant_count = sum(1 for _, v_count in completed_rows if v_count == 0)
    violation_count = sum(1 for _, v_count in completed_rows if v_count > 0)

    compliance_rate = round((compliant_count / len(completed_rows)) * 100, 2) if completed_rows else 100.0

    # 3. Violation severity breakdown
    viol_stmt = select(Violation.severity, func.count(Violation.id)).group_by(Violation.severity)
    if current_user.role == "officer":
        viol_stmt = viol_stmt.join(Inspection, Violation.inspection_id == Inspection.id).where(
            Inspection.officer_id == current_user.id
        )

    viol_res = await db.execute(viol_stmt)
    sev_counts: dict[str, int] = {str(r[0]): int(r[1]) for r in viol_res.all()}

    total_violations = sum(sev_counts.values())
    critical_violations = sev_counts.get("critical", 0)
    major_violations = sev_counts.get("major", 0)
    moderate_violations = sev_counts.get("moderate", 0)

    # 4. Total audit overrides
    audit_stmt = select(func.count(AuditLog.id))
    if current_user.role == "officer":
        audit_stmt = audit_stmt.where(AuditLog.actor_user_id == current_user.id)
    audit_res = await db.execute(audit_stmt)
    total_audit_overrides = audit_res.scalar() or 0

    # 5. Active officers
    officer_stmt = select(func.count(distinct(Inspection.officer_id)))
    officer_res = await db.execute(officer_stmt)
    active_officers_count = officer_res.scalar() or 0

    return AnalyticsSummaryResponse(
        total_inspections=total_inspections,
        completed_inspections=completed_inspections,
        needs_review_inspections=needs_review_inspections,
        draft_inspections=draft_inspections,
        compliant_inspections=compliant_count,
        violation_inspections=violation_count,
        overall_compliance_rate=compliance_rate,
        total_violations=total_violations,
        critical_violations=critical_violations,
        major_violations=major_violations,
        moderate_violations=moderate_violations,
        total_audit_overrides=total_audit_overrides,
        active_officers_count=active_officers_count,
    )


@router.get("/compliance-trends", response_model=ComplianceTrendsResponse)
async def get_compliance_trends(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    category: str | None = Query(default=None),
    region: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ComplianceTrendsResponse:
    """
    Time-series compliance trends over time (E2-05).
    """
    stmt = (
        select(
            func.date(Inspection.created_at).label("insp_date"),
            Inspection.id,
            func.count(Violation.id).label("violation_count"),
        )
        .outerjoin(Violation, Inspection.id == Violation.inspection_id)
        .group_by(func.date(Inspection.created_at), Inspection.id)
        .order_by(func.date(Inspection.created_at).asc())
    )

    if start_date:
        stmt = stmt.where(Inspection.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Inspection.created_at <= end_date)
    if category:
        stmt = stmt.where(Inspection.commodity_category == category)
    if region:
        stmt = stmt.join(User, Inspection.officer_id == User.id).where(User.region == region)
    elif current_user.role == "officer":
        stmt = stmt.where(Inspection.officer_id == current_user.id)

    res = await db.execute(stmt)
    rows = res.all()

    # Aggregate by date in python for portability
    by_date: dict[str, dict[str, int]] = {}
    for insp_date, _, v_count in rows:
        date_str = str(insp_date)
        if date_str not in by_date:
            by_date[date_str] = {"total": 0, "compliant": 0, "violation": 0}
        by_date[date_str]["total"] += 1
        if v_count == 0:
            by_date[date_str]["compliant"] += 1
        else:
            by_date[date_str]["violation"] += 1

    points = []
    for date_str, stats in sorted(by_date.items()):
        total = stats["total"]
        comp = stats["compliant"]
        rate = round((comp / total) * 100, 2) if total > 0 else 100.0
        points.append(
            ComplianceTrendPoint(
                date=date_str,
                total_inspections=total,
                compliant_count=comp,
                violation_count=stats["violation"],
                compliance_rate=rate,
            )
        )

    period_start_str = str(start_date.date()) if start_date else (points[0].date if points else None)
    period_end_str = str(end_date.date()) if end_date else (points[-1].date if points else None)

    return ComplianceTrendsResponse(
        points=points,
        period_start=period_start_str,
        period_end=period_end_str,
    )


@router.get("/violation-hotspots", response_model=ViolationHotspotsResponse)
async def get_violation_hotspots(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ViolationHotspotsResponse:
    """
    Identify violation hotspots by Rule, Commodity Category, and Region (E2-05).
    """
    # 1. Hotspots by Rule
    rule_stmt = (
        select(
            Violation.rule_id,
            func.min(Violation.citation).label("citation"),
            func.min(Violation.description).label("description"),
            func.min(Violation.severity).label("severity"),
            func.count(Violation.id).label("v_count"),
        )
        .group_by(Violation.rule_id)
        .order_by(func.count(Violation.id).desc())
        .limit(limit)
    )
    rule_res = await db.execute(rule_stmt)
    by_rule = [
        RuleViolationHotspot(
            rule_id=r.rule_id,
            citation=r.citation,
            description=r.description,
            severity=r.severity,
            count=r.v_count,
        )
        for r in rule_res.all()
    ]

    # 2. Hotspots by Commodity Category
    cat_stmt = (
        select(
            Inspection.commodity_category,
            func.count(distinct(Inspection.id)).label("total_inspections"),
            func.count(Violation.id).label("violations_count"),
        )
        .outerjoin(Violation, Inspection.id == Violation.inspection_id)
        .group_by(Inspection.commodity_category)
        .order_by(func.count(Violation.id).desc())
    )
    cat_res = await db.execute(cat_stmt)
    by_category = []
    for r in cat_res.all():
        total = r.total_inspections or 0
        v_count = r.violations_count or 0
        comp_rate = round(max(0.0, (total - v_count) / total * 100), 2) if total > 0 else 100.0
        by_category.append(
            CategoryViolationHotspot(
                commodity_category=r.commodity_category or "general",
                total_inspections=total,
                violations_count=v_count,
                compliance_rate=comp_rate,
            )
        )

    # 3. Hotspots by Region
    reg_stmt = (
        select(
            User.region,
            func.count(distinct(Inspection.id)).label("total_inspections"),
            func.count(Violation.id).label("violations_count"),
        )
        .join(Inspection, User.id == Inspection.officer_id)
        .outerjoin(Violation, Inspection.id == Violation.inspection_id)
        .group_by(User.region)
        .order_by(func.count(Violation.id).desc())
    )
    reg_res = await db.execute(reg_stmt)
    by_region = []
    for r in reg_res.all():
        region_name = r.region or "Unassigned"
        total = r.total_inspections or 0
        v_count = r.violations_count or 0
        comp_rate = round(max(0.0, (total - v_count) / total * 100), 2) if total > 0 else 100.0
        by_region.append(
            RegionViolationHotspot(
                region=region_name,
                total_inspections=total,
                violations_count=v_count,
                compliance_rate=comp_rate,
            )
        )

    return ViolationHotspotsResponse(
        by_rule=by_rule,
        by_category=by_category,
        by_region=by_region,
    )


@router.get("/officer-throughput", response_model=OfficerThroughputResponse)
async def get_officer_throughput(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_supervisor),
) -> OfficerThroughputResponse:
    """
    Officer inspection throughput and review audit metrics (E2-05 / US-09).
    Restricted to supervisors and admins.
    """
    officer_stmt = select(User).where(User.role.in_(["officer", "supervisor"]))
    officer_res = await db.execute(officer_stmt)
    officers = officer_res.scalars().all()

    throughput_items: list[OfficerThroughputItem] = []

    for off in officers:
        # Inspections by this officer
        insp_stmt = (
            select(
                Inspection.status,
                func.count(Inspection.id),
                func.max(Inspection.created_at),
            )
            .where(Inspection.officer_id == off.id)
            .group_by(Inspection.status)
        )
        insp_res = await db.execute(insp_stmt)
        rows = insp_res.all()

        total = sum(r[1] for r in rows)
        completed = sum(r[1] for r in rows if r[0] == "completed")
        needs_review = sum(r[1] for r in rows if r[0] == "needs_review")
        last_at = max((r[2] for r in rows if r[2] is not None), default=None)

        # Overrides by this officer
        audit_stmt = select(func.count(AuditLog.id)).where(AuditLog.actor_user_id == off.id)
        audit_res = await db.execute(audit_stmt)
        overrides = audit_res.scalar() or 0

        throughput_items.append(
            OfficerThroughputItem(
                officer_id=off.id,
                officer_name=off.full_name,
                email=off.email,
                region=off.region,
                total_inspections=total,
                completed_inspections=completed,
                needs_review_inspections=needs_review,
                human_overrides_count=overrides,
                last_inspection_at=last_at,
            )
        )

    return OfficerThroughputResponse(
        officers=throughput_items,
        total_active_officers=len(throughput_items),
    )
