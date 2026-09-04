"""API endpoints for eMaap National Legal Metrology Portal integration (E4-05, ADR-020)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user, get_db
from app.models.base import AuditLog, Inspection, User
from app.schemas.emaap import (
    EMaapAdapterStatusResponse,
    EMaapDocketSubmissionRequest,
    EMaapDocketSubmissionResponse,
    EMaapRegistrationLookupRequest,
    EMaapRegistrationResponse,
)
from app.services.evidence.verification import EvidenceVerificationService
from app.services.integrations.emaap import EMaapAdapter

router = APIRouter()


@router.get("/status", response_model=EMaapAdapterStatusResponse)
async def get_emaap_status(
    current_user: User = Depends(get_current_active_user),
) -> EMaapAdapterStatusResponse:
    """Returns the operational status, mode (live vs. sandbox), and supported capabilities of the eMaap adapter."""
    adapter = EMaapAdapter()
    return adapter.get_status()


@router.post("/verify-registration", response_model=EMaapRegistrationResponse)
async def verify_packer_registration(
    payload: EMaapRegistrationLookupRequest,
    current_user: User = Depends(get_current_active_user),
) -> EMaapRegistrationResponse:
    """
    Validates a Manufacturer/Packer/Importer registration number against the eMaap registry.
    Can be used by officers during inspection or automated cross-matching to check Rule 27 registration compliance.
    """
    adapter = EMaapAdapter()
    return await adapter.verify_packer_registration(
        registration_number=payload.registration_number,
        company_name=payload.company_name,
    )


@router.post("/dockets/{inspection_id}", response_model=EMaapDocketSubmissionResponse)
async def submit_inspection_docket_to_emaap(
    inspection_id: uuid.UUID,
    payload: EMaapDocketSubmissionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> EMaapDocketSubmissionResponse:
    """
    Submits a finalized non-compliant inspection case file and cryptographic evidence dossier
    to the National eMaap Portal for compounding proceedings and judicial prosecution.
    """
    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
            selectinload(Inspection.officer),
        )
    )
    res = await db.execute(stmt)
    inspection = res.scalar_one_or_none()

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection {inspection_id} not found",
        )

    if inspection.officer_id != current_user.id and current_user.role not in ["supervisor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to file this inspection into eMaap",
        )

    # 1. Fetch relevant audit logs for evidentiary verification
    field_ids = {str(f.id) for f in inspection.fields}
    audit_stmt = select(AuditLog).order_by(AuditLog.created_at.asc())
    audit_res = await db.execute(audit_stmt)
    all_logs = audit_res.scalars().all()
    relevant_logs = [
        log
        for log in all_logs
        if (log.entity_type == "inspection" and log.entity_id == str(inspection.id))
        or (log.entity_type == "extracted_field" and log.entity_id in field_ids)
    ]

    # 2. Cryptographic evidence verification
    evidence_service = EvidenceVerificationService()
    verification = evidence_service.verify_evidence_chain(inspection=inspection, audit_logs=relevant_logs)

    # 3. Submit dossier to eMaap adapter
    adapter = EMaapAdapter()
    officer = inspection.officer or current_user
    officer_notes = payload.officer_notes if payload else None
    priority = payload.priority if payload else "ROUTINE"

    docket_resp = await adapter.submit_enforcement_docket(
        inspection=inspection,
        officer=officer,
        verification_result=verification,
        officer_notes=officer_notes,
        priority=priority,
    )

    # 4. Record append-only audit trail event
    audit_entry = AuditLog(
        actor_user_id=current_user.id,
        action="emaap_docket_submitted",
        entity_type="inspection",
        entity_id=str(inspection.id),
        before_value=None,
        after_value={
            "docket_id": docket_resp.docket_id,
            "status": docket_resp.status,
            "is_sandbox": docket_resp.is_sandbox,
            "evidence_chain_hash": docket_resp.evidence_chain_hash,
        },
    )
    db.add(audit_entry)
    await db.commit()

    return docket_resp
