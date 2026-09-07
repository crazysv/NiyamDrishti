import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_admin, get_current_active_user, get_db
from app.models.base import AuditLog, RulePack, User
from app.schemas.rule_pack import (
    RulePackCreate,
    RulePackDetailRead,
    RulePackSummaryRead,
)
from app.services.rules import RulePackSchema, load_default_rule_pack

router = APIRouter()


@router.get("", response_model=list[RulePackSummaryRead])
async def list_rule_packs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[RulePackSummaryRead]:
    """
    List all available rule pack versions (RULE-05).
    """
    stmt = select(RulePack).order_by(RulePack.created_at.desc())
    result = await db.execute(stmt)
    packs = list(result.scalars().all())

    summaries = []
    for p in packs:
        rules_list = p.rules_json.get("rules", []) if isinstance(p.rules_json, dict) else []
        summaries.append(
            RulePackSummaryRead(
                version=p.version,
                effective_from=p.effective_from,
                effective_to=p.effective_to,
                source_citation=p.source_citation,
                is_active=p.is_active,
                created_by=p.created_by,
                created_at=p.created_at,
                rule_count=len(rules_list),
            )
        )
    return summaries


@router.get("/active", response_model=RulePackDetailRead)
async def get_active_rule_pack(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RulePack:
    """
    Get the currently active rule pack (RULE-05).
    """
    stmt = select(RulePack).where(RulePack.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    pack = result.scalar_one_or_none()

    if pack is None:
        # Fallback to default pack if DB is not seeded
        default_pack = load_default_rule_pack()
        now = datetime.now(timezone.utc)
        effective_from = datetime.combine(default_pack.effective_from, datetime.min.time(), tzinfo=timezone.utc)
        return RulePack(
            version=default_pack.rule_pack_version,
            effective_from=effective_from,
            effective_to=None,
            source_citation=default_pack.source_citation,
            rules_json=default_pack.model_dump(mode="json"),
            is_active=True,
            created_by=current_user.id,
            created_at=now,
        )

    return pack


@router.get("/{version}", response_model=RulePackDetailRead)
async def get_rule_pack_by_version(
    version: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RulePack:
    """
    Get a specific rule pack by its version identifier (RULE-05).
    """
    stmt = select(RulePack).where(RulePack.version == version)
    result = await db.execute(stmt)
    pack = result.scalar_one_or_none()

    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule pack version '{version}' not found",
        )

    return pack


@router.post("", response_model=RulePackDetailRead, status_code=status.HTTP_201_CREATED)
async def create_rule_pack(
    payload: RulePackCreate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_active_admin),
) -> RulePack:
    """
    Upload and validate a new versioned rule pack (RULE-01, RULE-06).
    Restricted to admin users. Audited in audit_logs.
    """
    # 1. JSON Schema validation
    try:
        validated_schema = RulePackSchema(**payload.rules_json)
    except ValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid rule pack JSON schema: {err}",
        )

    if payload.version != validated_schema.rule_pack_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload version '{payload.version}' does not match rules_json version '{validated_schema.rule_pack_version}'",
        )

    # 2. Check for collision
    stmt = select(RulePack).where(RulePack.version == payload.version)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rule pack version '{payload.version}' already exists",
        )

    # 3. Create RulePack
    new_pack = RulePack(
        version=payload.version,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        source_citation=payload.source_citation,
        rules_json=validated_schema.model_dump(mode="json"),
        is_active=False,
        created_by=admin_user.id,
    )
    db.add(new_pack)

    # 4. Immutable audit log write
    audit_entry = AuditLog(
        id=uuid.uuid4(),
        actor_user_id=admin_user.id,
        action="rule_pack_created",
        entity_type="rule_pack",
        entity_id=payload.version,
        before_value=None,
        after_value={
            "version": payload.version,
            "rule_count": len(validated_schema.rules),
            "effective_from": payload.effective_from.isoformat(),
        },
    )
    db.add(audit_entry)

    await db.commit()
    await db.refresh(new_pack)
    return new_pack


@router.post("/{version}/activate", response_model=RulePackDetailRead)
async def activate_rule_pack(
    version: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_active_admin),
) -> RulePack:
    """
    Activate a rule pack version (RULE-06).
    Deactivates any previously active rule pack and logs to audit_logs.
    Restricted to admin users.
    """
    stmt = select(RulePack).where(RulePack.version == version)
    result = await db.execute(stmt)
    target_pack = result.scalar_one_or_none()

    if target_pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule pack version '{version}' not found",
        )

    # Find current active version for audit logging
    active_stmt = select(RulePack).where(RulePack.is_active == True)  # noqa: E712
    active_result = await db.execute(active_stmt)
    current_active = active_result.scalar_one_or_none()
    previous_active_version = current_active.version if current_active else None

    # Deactivate all and activate target
    await db.execute(update(RulePack).values(is_active=False))
    target_pack.is_active = True

    # Audit log
    audit_entry = AuditLog(
        id=uuid.uuid4(),
        actor_user_id=admin_user.id,
        action="rule_pack_activated",
        entity_type="rule_pack",
        entity_id=version,
        before_value={"previous_active_version": previous_active_version},
        after_value={"active_version": version},
    )
    db.add(audit_entry)

    await db.commit()
    await db.refresh(target_pack)
    return target_pack
