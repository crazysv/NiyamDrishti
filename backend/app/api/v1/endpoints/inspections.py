import hashlib
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user, get_db
from app.core.config import get_field_confidence_threshold, settings
from app.models.base import AuditLog, ExtractedField, Inspection, InspectionImage, Report, RulePack, User, Violation
from app.schemas.inspection import (
    AuditLogRead,
    BatchFieldReviewRequest,
    BatchFieldReviewResponse,
    EvidenceItemRead,
    ExtractedFieldRead,
    FieldReviewResponse,
    FieldReviewUpdate,
    InspectionCreate,
    InspectionEvidenceRead,
    InspectionImageCreate,
    InspectionImageRead,
    InspectionListResponse,
    InspectionRead,
    InspectionReviewQueueResponse,
    InspectionSummaryRead,
    ReportFormatType,
    ReportGenerateRequest,
    ReportRead,
    ReviewQueueItemRead,
    ViolationRead,
)
from app.services.calibration import OpticalCalibrationService
from app.services.extraction import (
    DeclarationExtractionService,
    ExtractedDeclaration,
    list_categories,
)
from app.services.cross_matching import MultiImageCrossMatchingService
from app.services.cross_matching.schemas import CrossMatchReport
from app.services.ocr import OCRService
from app.services.reporting.service import ReportService
from app.services.rules import RuleEngine
from app.services.rules.schemas import EvaluationSummary
from app.services.storage import (
    UPLOAD_DIR,
    generate_presigned_download_url,
    get_image_bytes,
    parse_data_url,
    save_image_bytes,
    save_report_bytes,
)
from app.schemas.sync import (
    BatchOfflineSyncRequest,
    BatchOfflineSyncResponse,
    OfflineConflictDetail,
    OfflineSyncInspectionItem,
    OfflineSyncResult,
)
from app.core.metrics import (
    record_ocr_duration,
    record_rule_evaluation_duration,
    record_inspection_completed,
    record_offline_sync,
)
from app.schemas.evidence_verification import (
    EvidenceVerificationResult,
    Section65BCertificate,
)
from app.services.evidence import EvidenceVerificationService

router = APIRouter()

ALLOWED_IMAGE_ROLES = {"front_pdp", "back_panel", "side_panel", "sticker", "ecommerce_listing"}


@router.post("", response_model=InspectionRead, status_code=status.HTTP_201_CREATED)
async def create_inspection(
    payload: InspectionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Inspection:
    """
    Creates a new inspection record.
    Supports idempotency via Idempotency-Key header or payload.client_id (E4-02).
    Freezes the active rule pack version at creation time.
    """
    client_id = request.headers.get("idempotency-key") or payload.client_id
    if client_id:
        existing_stmt = (
            select(Inspection)
            .where(Inspection.officer_id == current_user.id, Inspection.client_id == client_id)
            .options(
                selectinload(Inspection.images),
                selectinload(Inspection.fields),
                selectinload(Inspection.violations),
            )
        )
        existing_res = await db.execute(existing_stmt)
        existing_inspection = existing_res.scalar_one_or_none()
        if existing_inspection:
            return existing_inspection

    active_stmt = select(RulePack.version).where(RulePack.is_active == True)  # noqa: E712
    active_res = await db.execute(active_stmt)
    db_active_version = active_res.scalar_one_or_none()
    rule_pack_version = db_active_version or settings.ACTIVE_RULE_PACK_VERSION or "2026.02.01"

    status_val = "sync_pending" if payload.captured_offline else "draft"
    created_at_val = payload.created_at or datetime.now(timezone.utc)

    inspection = Inspection(
        officer_id=current_user.id,
        status=status_val,
        commodity_category=payload.commodity_category,
        rule_pack_version=rule_pack_version,
        is_self_check=payload.is_self_check,
        region=current_user.region,
        captured_offline=payload.captured_offline,
        created_at=created_at_val,
        client_id=client_id,
    )

    db.add(inspection)
    await db.commit()

    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection.id)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
        )
    )
    result = await db.execute(stmt)
    created_inspection = result.scalar_one()
    return created_inspection


@router.get(
    "",
    response_model=InspectionListResponse,
    summary="Search and filter inspections (SRCH-01)",
)
async def list_inspections(
    officer_id: uuid.UUID | None = Query(None, description="Filter by officer UUID"),
    officer_name: str | None = Query(None, description="Search by officer name substring"),
    date_from: datetime | None = Query(None, description="Filter inspections created on or after"),
    date_to: datetime | None = Query(None, description="Filter inspections created on or before"),
    region: str | None = Query(None, description="Filter by enforcement region"),
    commodity_category: str | None = Query(None, description="Filter by commodity category"),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status (completed, needs_review, draft, sync_pending)"
    ),
    violation_type: str | None = Query(None, description="Filter by violation rule ID or description substring"),
    has_violations: bool | None = Query(None, description="Filter by presence of statutory violations"),
    product_query: str | None = Query(
        None, description="Search by product, brand, or manufacturer text in extracted fields"
    ),
    is_self_check: bool | None = Query(
        False, description="Filter self-checks vs official enforcement inspections (default: False)"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> InspectionListResponse:
    """
    Search and filter inspections with support for officer scoping, date ranges,
    regions, violation types, and product text search (SRCH-01).
    """
    filters = []

    if is_self_check is not None:
        filters.append(Inspection.is_self_check == is_self_check)

    # RBAC Enforcement: Regular officers can only access their own inspections
    if current_user.role == "officer":
        filters.append(Inspection.officer_id == current_user.id)
    elif officer_id:
        filters.append(Inspection.officer_id == officer_id)

    if officer_name:
        filters.append(Inspection.officer.has(User.full_name.ilike(f"%{officer_name}%")))

    if date_from:
        filters.append(Inspection.created_at >= date_from)
    if date_to:
        filters.append(Inspection.created_at <= date_to)

    if region:
        filters.append(Inspection.region.ilike(f"%{region}%"))

    if commodity_category:
        filters.append(Inspection.commodity_category == commodity_category)

    if status_filter:
        filters.append(Inspection.status == status_filter)

    if has_violations is True:
        filters.append(Inspection.violations.any())
    elif has_violations is False:
        filters.append(~Inspection.violations.any())

    if violation_type:
        filters.append(
            Inspection.violations.any(
                or_(
                    Violation.rule_id.ilike(f"%{violation_type}%"),
                    Violation.description.ilike(f"%{violation_type}%"),
                    Violation.citation.ilike(f"%{violation_type}%"),
                )
            )
        )

    if product_query:
        filters.append(
            Inspection.fields.any(
                or_(
                    ExtractedField.raw_text.ilike(f"%{product_query}%"),
                    ExtractedField.parsed_value.ilike(f"%{product_query}%"),
                    ExtractedField.officer_override_value.ilike(f"%{product_query}%"),
                )
            )
        )

    # 1. Count total matching rows
    count_stmt = select(func.count(distinct(Inspection.id)))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total_res = await db.execute(count_stmt)
    total = total_res.scalar_one()

    # 2. Fetch paginated records with eager loading
    query_stmt = (
        select(Inspection)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
            selectinload(Inspection.officer),
        )
        .order_by(Inspection.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if filters:
        query_stmt = query_stmt.where(*filters)

    records_res = await db.execute(query_stmt)
    inspections = records_res.scalars().all()

    summary_items = []
    for insp in inspections:
        # Determine front PDP thumbnail
        thumb_url = None
        if insp.images:
            front_img = next((img for img in insp.images if img.image_role == "front_pdp"), insp.images[0])
            if front_img.storage_url.startswith("local://"):
                thumb_url = f"/api/v1/inspections/{insp.id}/images/{front_img.id}/file"
            elif front_img.storage_url.startswith("/uploads/"):
                thumb_url = front_img.storage_url
            else:
                thumb_url = generate_presigned_download_url(front_img.storage_url)

        violations_cnt = len(insp.violations)
        verdict = (
            "non_compliant"
            if violations_cnt > 0
            else ("needs_review" if insp.status == "needs_review" else "compliant")
        )

        summary_items.append(
            InspectionSummaryRead(
                id=insp.id,
                officer_id=insp.officer_id,
                officer_name=insp.officer.full_name if insp.officer else None,
                status=insp.status,
                commodity_category=insp.commodity_category,
                rule_pack_version=insp.rule_pack_version,
                is_self_check=insp.is_self_check,
                region=insp.region,
                captured_offline=insp.captured_offline,
                created_at=insp.created_at,
                updated_at=insp.updated_at,
                violations_count=violations_cnt,
                fields_count=len(insp.fields),
                images_count=len(insp.images),
                thumbnail_url=thumb_url,
                overall_verdict=verdict,
            )
        )

    return InspectionListResponse(
        items=summary_items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/{inspection_id}/images", response_model=InspectionImageRead, status_code=status.HTTP_201_CREATED)
async def upload_inspection_image(
    inspection_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> InspectionImage:
    """
    Upload an image for an inspection.
    Supports either JSON body with data_url (from offline sync/PWA) or multipart form-data file upload.
    """
    stmt = select(Inspection).where(Inspection.id == inspection_id)
    result = await db.execute(stmt)
    inspection = result.scalar_one_or_none()

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection {inspection_id} not found",
        )

    # Check authorization (officer or admin/supervisor)
    if inspection.officer_id != current_user.id and current_user.role not in ["supervisor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this inspection",
        )

    # Deterministic Conflict Handling (E4-02): Finalized inspection on server is immutable
    if inspection.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "INSPECTION_FINALIZED",
                "message": "Inspection is already completed and finalized. Cannot attach new images.",
                "inspection_id": str(inspection_id),
                "server_status": inspection.status,
                "suggested_resolution": "server_authoritative",
            },
        )

    content_type = request.headers.get("content-type", "")
    img_client_id: str | None = None

    if "application/json" in content_type:
        body = await request.json()
        try:
            payload = InspectionImageCreate(**body)
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {err}",
            )
        role = payload.image_role
        quality_passed = payload.quality_check_passed
        width_px = payload.width_px
        height_px = payload.height_px
        captured_at = payload.captured_at or datetime.now(timezone.utc)
        img_client_id = payload.client_id or request.headers.get("idempotency-key")

        if not payload.data_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing data_url in JSON payload",
            )
        try:
            ext, file_bytes = parse_data_url(payload.data_url)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid image data_url: {e}",
            )
        filename = f"{role}_{uuid.uuid4().hex[:8]}.{ext}"
        if width_px is None or height_px is None:
            try:
                import io
                from PIL import Image as PILImage
                with PILImage.open(io.BytesIO(file_bytes)) as pil_img:
                    width_px, height_px = pil_img.size
            except Exception:
                pass

    elif "multipart/form-data" in content_type:
        form = await request.form()
        role_val = form.get("image_role") or form.get("role")
        if not role_val or not isinstance(role_val, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing image_role in form data",
            )
        role = role_val  # type: ignore[assignment]
        upload_file = form.get("file")
        if not upload_file or not hasattr(upload_file, "read"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing file in form data",
            )
        file_bytes = await upload_file.read()
        filename = getattr(upload_file, "filename", None) or f"{role}_{uuid.uuid4().hex[:8]}.jpg"
        quality_passed = str(form.get("quality_check_passed", "true")).lower() == "true"
        w_val = form.get("width_px")
        h_val = form.get("height_px")
        width_px = int(str(w_val)) if w_val else None
        height_px = int(str(h_val)) if h_val else None
        captured_at = datetime.now(timezone.utc)
        raw_client_id = form.get("client_id")
        img_client_id = str(raw_client_id) if raw_client_id else request.headers.get("idempotency-key")
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/json or multipart/form-data",
        )

    if role not in ALLOWED_IMAGE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image_role '{role}'. Allowed roles: {', '.join(sorted(ALLOWED_IMAGE_ROLES))}",
        )

    # Idempotency check: if image with client_id already attached, return existing image (E4-02)
    if img_client_id:
        existing_img_stmt = select(InspectionImage).where(
            InspectionImage.inspection_id == inspection_id,
            InspectionImage.client_id == img_client_id,
        )
        existing_img_res = await db.execute(existing_img_stmt)
        existing_img = existing_img_res.scalar_one_or_none()
        if existing_img:
            return existing_img

    # Save to storage (local filesystem or R2)
    storage_url = await save_image_bytes(inspection_id, file_bytes, filename)

    # Derive optical scale calibration if standard barcode present
    calib_scale = None
    try:
        calib_service = OpticalCalibrationService()
        calib_res = calib_service.calibrate_image(file_bytes)
        if calib_res.is_calibrated and calib_res.scale_mm_per_px is not None:
            calib_scale = calib_res.scale_mm_per_px
    except Exception:
        pass

    # Compute cryptographic SHA-256 for Section 65B/BSA 63 digital chain of custody
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # Create record
    image_record = InspectionImage(
        inspection_id=inspection_id,
        image_role=role,
        storage_url=storage_url,
        width_px=width_px,
        height_px=height_px,
        calibration_scale_mm_per_px=calib_scale,
        quality_check_passed=quality_passed,
        captured_at=captured_at,
        client_id=img_client_id,
        sha256_hash=sha256_hash,
    )

    db.add(image_record)
    await db.commit()
    await db.refresh(image_record)

    return image_record


@router.post("/sync", response_model=BatchOfflineSyncResponse, status_code=status.HTTP_200_OK)
async def sync_offline_inspections(
    payload: BatchOfflineSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BatchOfflineSyncResponse:
    """
    Hardened batch offline synchronization endpoint (E4-02).
    Processes offline inspections and images atomically with idempotency,
    exponential retry recovery, and deterministic conflict resolution.
    """
    successful = 0
    conflicted = 0
    failed = 0
    results: list[OfflineSyncResult] = []

    active_stmt = select(RulePack.version).where(RulePack.is_active == True)  # noqa: E712
    active_res = await db.execute(active_stmt)
    db_active_version = active_res.scalar_one_or_none()
    rule_pack_version = db_active_version or settings.ACTIVE_RULE_PACK_VERSION or "2026.02.01"

    for item in payload.inspections:
        client_id = item.client_id
        try:
            existing_stmt = select(Inspection).where(
                Inspection.officer_id == current_user.id,
                Inspection.client_id == client_id,
            )
            existing_res = await db.execute(existing_stmt)
            existing_inspection = existing_res.scalar_one_or_none()

            if existing_inspection:
                inspection = existing_inspection
                if inspection.status == "completed":
                    conflict_detail = OfflineConflictDetail(
                        code="INSPECTION_FINALIZED",
                        message="Inspection is already finalized and completed on the server.",
                        inspection_id=str(inspection.id),
                        server_status=inspection.status,
                        suggested_resolution="server_authoritative",
                    )
                    conflicted += 1
                    record_offline_sync("inspection", "conflict")
                    results.append(
                        OfflineSyncResult(
                            success=True,
                            client_id=client_id,
                            inspection_id=inspection.id,
                            status=inspection.status,
                            images_synced=0,
                            images_skipped=len(item.images),
                            conflict=conflict_detail,
                        )
                    )
                    continue
            else:
                created_at_val = item.created_at or datetime.now(timezone.utc)
                inspection = Inspection(
                    officer_id=current_user.id,
                    status="sync_pending",
                    commodity_category=item.commodity_category,
                    rule_pack_version=rule_pack_version,
                    is_self_check=item.is_self_check,
                    region=item.region or current_user.region,
                    captured_offline=True,
                    created_at=created_at_val,
                    client_id=client_id,
                )
                db.add(inspection)
                await db.commit()
                await db.refresh(inspection)

            images_synced = 0
            images_skipped = 0

            for img_item in item.images:
                existing_img_stmt = select(InspectionImage).where(
                    InspectionImage.inspection_id == inspection.id,
                    InspectionImage.client_id == img_item.client_id,
                )
                existing_img = (await db.execute(existing_img_stmt)).scalar_one_or_none()

                if existing_img:
                    images_skipped += 1
                    continue

                try:
                    ext, file_bytes = parse_data_url(img_item.data_url)
                    filename = f"{img_item.image_role}_{uuid.uuid4().hex[:8]}.{ext}"
                    storage_url = await save_image_bytes(inspection.id, file_bytes, filename)
                    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

                    calib_scale = None
                    try:
                        calib_service = OpticalCalibrationService()
                        calib_res = calib_service.calibrate_image(file_bytes)
                        if calib_res.is_calibrated and calib_res.scale_mm_per_px is not None:
                            calib_scale = calib_res.scale_mm_per_px
                    except Exception:
                        pass

                    img_record = InspectionImage(
                        inspection_id=inspection.id,
                        client_id=img_item.client_id,
                        image_role=img_item.image_role,
                        storage_url=storage_url,
                        width_px=img_item.width_px,
                        height_px=img_item.height_px,
                        calibration_scale_mm_per_px=calib_scale,
                        quality_check_passed=img_item.quality_check_passed,
                        captured_at=img_item.captured_at or datetime.now(timezone.utc),
                        sha256_hash=sha256_hash,
                    )
                    db.add(img_record)
                    images_synced += 1
                except Exception:
                    images_skipped += 1

            inspection.synced_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(inspection)

            successful += 1
            record_offline_sync("inspection", "synced")
            if images_synced > 0:
                record_offline_sync("image", "synced", count=images_synced)
            if images_skipped > 0:
                record_offline_sync("image", "skipped", count=images_skipped)

            results.append(
                OfflineSyncResult(
                    success=True,
                    client_id=client_id,
                    inspection_id=inspection.id,
                    status=inspection.status,
                    images_synced=images_synced,
                    images_skipped=images_skipped,
                )
            )

        except Exception as e:
            failed += 1
            record_offline_sync("inspection", "failed")
            results.append(
                OfflineSyncResult(
                    success=False,
                    client_id=client_id,
                    status="failed",
                    error=str(e),
                )
            )

    return BatchOfflineSyncResponse(
        total=len(payload.inspections),
        successful=successful,
        conflicted=conflicted,
        failed=failed,
        results=results,
    )


@router.get("/categories")
async def get_commodity_categories(
    current_user: User = Depends(get_current_active_user),
) -> list[dict]:
    """
    List available commodity categories for manual or guided selection (EXT-09).
    """
    return list_categories()


@router.get("/{inspection_id}", response_model=InspectionRead)
async def get_inspection(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Inspection:
    """
    Get full inspection details by ID including images and extracted fields.
    """
    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
        )
    )
    result = await db.execute(stmt)
    inspection = result.scalar_one_or_none()

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection {inspection_id} not found",
        )

    if inspection.officer_id != current_user.id and current_user.role not in ["supervisor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this inspection",
        )

    return inspection


@router.post("/{inspection_id}/process", response_model=list[ExtractedFieldRead])
@router.post("/{inspection_id}/extract", response_model=list[ExtractedFieldRead])
async def extract_inspection_declarations(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ExtractedField]:
    """
    Trigger OCR and Legal Metrology declaration extraction for all images in an inspection.
    Saves results to extracted_fields and updates inspection status to needs_review.
    """
    stmt = select(Inspection).where(Inspection.id == inspection_id).options(selectinload(Inspection.images))
    result = await db.execute(stmt)
    inspection = result.scalar_one_or_none()

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection {inspection_id} not found",
        )

    if inspection.officer_id != current_user.id and current_user.role not in ["supervisor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this inspection",
        )

    if not inspection.images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inspection has no captured images to extract from",
        )

    ocr_service = OCRService()
    extraction_service = DeclarationExtractionService()
    all_declarations: list[ExtractedDeclaration] = []

    for img in inspection.images:
        # Load image bytes from R2/S3, HTTP, or local storage
        img_bytes = await get_image_bytes(img.storage_url, inspection.id)
        if not img_bytes:
            logger.warning(f"Could not load image bytes for image {img.id} ({img.storage_url})")
            continue

        # Calibrate image if scale not yet derived
        if img.calibration_scale_mm_per_px is None:
            try:
                calib_service = OpticalCalibrationService()
                calib_res = calib_service.calibrate_image(img_bytes)
                if calib_res.is_calibrated and calib_res.scale_mm_per_px is not None:
                    img.calibration_scale_mm_per_px = calib_res.scale_mm_per_px
            except Exception as calib_err:
                logger.warning(f"Calibration warning for image {img.id}: {calib_err}")

        try:
            t0_ocr = time.perf_counter()
            ocr_res = ocr_service.process_image(img_bytes, source_image_id=str(img.id))
            record_ocr_duration(time.perf_counter() - t0_ocr, engine="paddleocr", status="success")
            declarations = extraction_service.extract_from_ocr_result(ocr_res)
            all_declarations.extend(declarations)
        except Exception as ocr_err:
            logger.error(f"OCR processing failed for image {img.id}: {ocr_err}", exc_info=True)
            record_ocr_duration(0.0, engine="paddleocr", status="error")
            # Continue on error for other images
            pass

    # Save extracted fields to DB
    persisted = await extraction_service.save_extracted_fields(
        db=db,
        inspection_id=inspection.id,
        declarations=all_declarations,
        clear_existing=True,
    )

    # Automatically evaluate rules against frozen rule pack version and populate violations (EVID-02)
    pack_stmt = select(RulePack).where(RulePack.version == inspection.rule_pack_version)
    pack_res = await db.execute(pack_stmt)
    rule_pack = pack_res.scalar_one_or_none()

    rule_engine = RuleEngine()
    t0_rule = time.perf_counter()
    summary = rule_engine.evaluate_rules(
        fields=persisted,
        images=inspection.images,
        commodity_category=inspection.commodity_category,
        rule_pack=rule_pack or rule_engine.default_pack,
    )
    record_rule_evaluation_duration(time.perf_counter() - t0_rule, rule_pack_version=inspection.rule_pack_version)

    await db.execute(delete(Violation).where(Violation.inspection_id == inspection.id))
    for v in summary.violations:
        violation = Violation(
            id=uuid.uuid4(),
            inspection_id=inspection.id,
            extracted_field_id=v["extracted_field_id"],
            rule_id=v["rule_id"],
            rule_pack_version=v["rule_pack_version"],
            description=v["description"],
            citation=v["citation"],
            severity=v["severity"],
        )
        db.add(violation)

    # Multi-Image & E-Commerce Cross-Consistency Checking (E2-03, E3-02)
    cross_matching_service = MultiImageCrossMatchingService()
    cross_report = cross_matching_service.analyze_cross_image_consistency(
        inspection_id=inspection.id,
        images=inspection.images,
        fields=persisted,
    )
    if cross_report.discrepancies:
        cross_violations = cross_matching_service.to_violations(
            inspection_id=inspection.id,
            rule_pack_version=inspection.rule_pack_version,
            discrepancies=cross_report.discrepancies,
        )
        for cv in cross_violations:
            db.add(cv)

    has_cross_match_failure = not cross_report.is_consistent
    inspection.status = "completed" if (summary.overall_status == "pass" and not has_cross_match_failure) else "needs_review"
    record_inspection_completed(
        verdict="compliant" if inspection.status == "completed" else "non_compliant",
        category=inspection.commodity_category or "general",
        is_self_check=inspection.is_self_check,
    )
    await db.commit()

    return persisted


@router.get("/{inspection_id}/cross-match", response_model=CrossMatchReport)
async def get_inspection_cross_matching_report(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CrossMatchReport:
    """
    Analyzes cross-image and physical-to-listing declaration consistency (E2-03, E3-02).
    Cross-references front PDP, back panel, sticker, and e-commerce listing images for:
    - Altered MRP stickers (Rule 18(2))
    - E-commerce listing price inflation / overcharging (Rule 6(10) & Rule 18(2))
    - Physical package vs e-commerce listing net quantity mismatches (Rule 6(10))
    - Conflicting country of origin or manufacturer declarations across physical/digital channels
    """
    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(selectinload(Inspection.images), selectinload(Inspection.fields))
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
            detail="You do not have permission to view this inspection",
        )

    service = MultiImageCrossMatchingService()
    report = service.analyze_cross_image_consistency(
        inspection_id=inspection.id,
        images=inspection.images,
        fields=inspection.fields,
    )
    return report


@router.get("/{inspection_id}/fields", response_model=list[ExtractedFieldRead])
async def get_inspection_fields(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ExtractedField]:
    """
    List extracted fields for a given inspection.
    """
    stmt = select(Inspection).where(Inspection.id == inspection_id)
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
            detail="You do not have permission to view this inspection",
        )

    field_stmt = select(ExtractedField).where(ExtractedField.inspection_id == inspection_id)
    field_res = await db.execute(field_stmt)
    return list(field_res.scalars().all())


@router.post("/{inspection_id}/evaluate", response_model=EvaluationSummary)
async def evaluate_inspection_rules(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> EvaluationSummary:
    """
    Evaluate all extracted fields for an inspection against the frozen rule pack version (RULE-04, RULE-07).
    Populates violations table (EVID-02) and updates inspection status.
    """
    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
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
            detail="You do not have permission to evaluate this inspection",
        )

    # 1. Fetch frozen rule pack version (RULE-07 invariant)
    pack_stmt = select(RulePack).where(RulePack.version == inspection.rule_pack_version)
    pack_res = await db.execute(pack_stmt)
    rule_pack = pack_res.scalar_one_or_none()

    rule_engine = RuleEngine()

    # 2. Evaluate rules
    summary = rule_engine.evaluate_rules(
        fields=inspection.fields,
        images=inspection.images,
        commodity_category=inspection.commodity_category,
        rule_pack=rule_pack or rule_engine.default_pack,
    )

    # 3. Clear existing violations for this inspection
    await db.execute(delete(Violation).where(Violation.inspection_id == inspection.id))

    # 4. Populate violations table from rule engine output (EVID-02)
    for v in summary.violations:
        violation = Violation(
            id=uuid.uuid4(),
            inspection_id=inspection.id,
            extracted_field_id=v["extracted_field_id"],
            rule_id=v["rule_id"],
            rule_pack_version=v["rule_pack_version"],
            description=v["description"],
            citation=v["citation"],
            severity=v["severity"],
        )
        db.add(violation)

    # 5. Update inspection status based on overall evaluation
    if summary.overall_status == "pass":
        inspection.status = "completed"
    else:
        inspection.status = "needs_review"

    await db.commit()
    return summary


FIELD_LABELS: dict[str, str] = {
    "mrp": "MRP",
    "net_quantity": "NET QUANTITY",
    "mfg_date": "DATE OF MFG",
    "manufacturer_address": "MANUFACTURER",
    "consumer_care": "CONSUMER CARE",
    "country_of_origin": "ORIGIN",
    "commodity_name": "COMMODITY NAME",
    "retail_sale_price": "RETAIL SALE PRICE",
}


@router.get("/{inspection_id}/images/{image_id}/file")
async def get_inspection_image_file(
    inspection_id: uuid.UUID,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> FileResponse:
    """Serve the raw image file for inspection evidence display."""
    stmt = (
        select(InspectionImage).join(Inspection).where(InspectionImage.id == image_id, Inspection.id == inspection_id)
    )
    res = await db.execute(stmt)
    img = res.scalar_one_or_none()

    if img is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    clean_path = img.storage_url.replace("local://", "").lstrip("/").replace("uploads/", "")
    full_path = UPLOAD_DIR / clean_path

    if not full_path.exists():
        # Check direct upload dir
        alt_path = UPLOAD_DIR / str(inspection_id) / clean_path
        if alt_path.exists():
            full_path = alt_path
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image file not found on disk at {full_path}",
            )

    return FileResponse(path=full_path)


@router.get("/{inspection_id}/evidence", response_model=InspectionEvidenceRead)
async def get_inspection_evidence(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> InspectionEvidenceRead:
    """
    Returns visual evidence mapping binding all extracted declarations and legal violations
    to source image bounding boxes with normalized coordinates (EVID-01).
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
            detail="You do not have permission to view evidence for this inspection",
        )

    # Primary image (front PDP preferred)
    front_img = None
    for img in inspection.images:
        if img.image_role == "front_pdp":
            front_img = img
            break
    if front_img is None and len(inspection.images) > 0:
        front_img = inspection.images[0]

    img_w = float(front_img.width_px or 1200) if front_img else 1200.0
    img_h = float(front_img.height_px or 1600) if front_img else 1600.0
    calib_scale = (
        float(front_img.calibration_scale_mm_per_px) if (front_img and front_img.calibration_scale_mm_per_px) else None
    )

    # Image lookup
    img_map = {img.id: img for img in inspection.images}

    # Violations lookup by field_id
    field_violations: dict[uuid.UUID, list[ViolationRead]] = {}
    for v in inspection.violations:
        if v.extracted_field_id:
            if v.extracted_field_id not in field_violations:
                field_violations[v.extracted_field_id] = []
            field_violations[v.extracted_field_id].append(
                ViolationRead(
                    id=v.id,
                    inspection_id=v.inspection_id,
                    extracted_field_id=v.extracted_field_id,
                    rule_id=v.rule_id,
                    rule_pack_version=v.rule_pack_version,
                    description=v.description,
                    citation=v.citation,
                    severity=v.severity,
                    created_at=v.created_at,
                )
            )

    items: list[EvidenceItemRead] = []
    order_keys = [
        "mrp",
        "net_quantity",
        "mfg_date",
        "manufacturer_address",
        "consumer_care",
        "country_of_origin",
        "commodity_name",
    ]
    sorted_fields = sorted(
        inspection.fields,
        key=lambda f: order_keys.index(f.field_type) if f.field_type in order_keys else 99,
    )

    passed_count = 0
    review_count = 0
    failed_count = 0
    product_name = None

    for idx, f in enumerate(sorted_fields):
        evidence_tag = f"E{idx + 1:02d}"
        if f.field_type == "commodity_name" and f.parsed_value:
            product_name = f.parsed_value

        src_img = img_map.get(f.source_image_id, front_img)
        cur_w = float(src_img.width_px or img_w) if src_img else img_w
        cur_h = float(src_img.height_px or img_h) if src_img else img_h
        cur_scale = (
            float(src_img.calibration_scale_mm_per_px)
            if (src_img and src_img.calibration_scale_mm_per_px)
            else calib_scale
        )

        raw_box = f.bounding_box or {}
        x_px = float(raw_box.get("x", raw_box.get("left", 0.0)))
        y_px = float(raw_box.get("y", raw_box.get("top", 0.0)))
        w_px = float(raw_box.get("w", raw_box.get("width", 100.0)))
        h_px = float(raw_box.get("h", raw_box.get("height", 30.0)))

        left_pct = round((x_px / cur_w) * 100, 2) if cur_w > 0 else 0.0
        top_pct = round((y_px / cur_h) * 100, 2) if cur_h > 0 else 0.0
        width_pct = round((w_px / cur_w) * 100, 2) if cur_w > 0 else 20.0
        height_pct = round((h_px / cur_h) * 100, 2) if cur_h > 0 else 5.0

        normalized_bbox = {
            "x": x_px,
            "y": y_px,
            "w": w_px,
            "h": h_px,
            "left_pct": left_pct,
            "top_pct": top_pct,
            "width_pct": width_pct,
            "height_pct": height_pct,
        }

        measured_dim: dict[str, Any] | None = None
        if cur_scale is not None and cur_scale > 0:
            measured_dim = {
                "height_mm": round(h_px * cur_scale, 2),
                "scale_mm_per_px": cur_scale,
                "is_calibrated": True,
                "warning": None,
            }
        else:
            pdp_ratio = round(h_px / cur_h, 4) if cur_h > 0 else 0.0
            measured_dim = {
                "height_mm": None,
                "pdp_ratio": pdp_ratio,
                "is_calibrated": False,
                "warning": "Uncalibrated measurement: barcode reference missing",
            }

        v_list = field_violations.get(f.id, [])
        has_fail_violation = any(
            v.severity in ("critical", "major") and "review" not in v.description.lower() for v in v_list
        )

        if f.verdict == "fail" or has_fail_violation:
            item_verdict = "fail"
            failed_count += 1
        elif f.verdict == "needs_review" or len(v_list) > 0:
            item_verdict = "needs_review"
            review_count += 1
        else:
            item_verdict = "pass"
            passed_count += 1

        label = FIELD_LABELS.get(f.field_type, f.field_type.replace("_", " ").upper())

        display_url = ""
        if src_img:
            if src_img.storage_url.startswith("local://"):
                display_url = f"/api/v1/inspections/{inspection.id}/images/{src_img.id}/file"
            else:
                display_url = src_img.storage_url

        items.append(
            EvidenceItemRead(
                item_id=evidence_tag,
                field_id=f.id,
                field_type=f.field_type,
                field_label=label,
                raw_text=f.raw_text,
                parsed_value=f.parsed_value,
                confidence=f.confidence,
                verdict=item_verdict,
                bounding_box=normalized_bbox,
                source_image_id=f.source_image_id,
                source_image_url=display_url,
                is_calibrated=cur_scale is not None,
                measured_dimension=measured_dim,
                violations=v_list,
            )
        )

    if not product_name:
        category_name = (inspection.commodity_category or "Packaged Commodity").replace("_", " ").title()
        product_name = f"Inspected {category_name}"

    overall = "violations_found" if failed_count > 0 else ("needs_review" if review_count > 0 else "compliant")

    primary_url = ""
    if front_img:
        if front_img.storage_url.startswith("local://"):
            primary_url = f"/api/v1/inspections/{inspection.id}/images/{front_img.id}/file"
        elif front_img.storage_url.startswith("/uploads/"):
            primary_url = front_img.storage_url
        else:
            primary_url = generate_presigned_download_url(front_img.storage_url)

    officer_name = inspection.officer.full_name if inspection.officer else "Legal Metrology Officer"

    return InspectionEvidenceRead(
        inspection_id=inspection.id,
        product_name=product_name,
        commodity_category=inspection.commodity_category or "general",
        overall_status=overall,
        rule_pack_version=inspection.rule_pack_version,
        officer_id=inspection.officer_id,
        officer_name=officer_name,
        primary_image_url=primary_url,
        primary_image_dimensions={"width": img_w, "height": img_h},
        items=items,
        stats={
            "total": len(items),
            "passed": passed_count,
            "review": review_count,
            "failed": failed_count,
        },
    )


@router.get("/{inspection_id}/evidence/verify", response_model=EvidenceVerificationResult)
async def verify_inspection_evidence(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> EvidenceVerificationResult:
    """
    Cryptographically audits and verifies the evidence chain of custody (E4-04).
    Validates SHA-256 fingerprints on all captured label photographs, verifies
    tamper-evident audit log chaining, and returns master cryptographic digest.
    """
    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
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
            detail="You do not have permission to verify evidence for this inspection",
        )

    audit_stmt = select(AuditLog).order_by(AuditLog.created_at.asc())
    audit_res = await db.execute(audit_stmt)
    all_logs = audit_res.scalars().all()

    field_ids = {str(f.id) for f in inspection.fields}
    relevant_logs = [
        log for log in all_logs
        if (log.entity_type == "inspection" and log.entity_id == str(inspection.id))
        or (log.entity_type == "extracted_field" and log.entity_id in field_ids)
    ]

    service = EvidenceVerificationService()
    return service.verify_evidence_chain(inspection=inspection, audit_logs=relevant_logs)


@router.get("/{inspection_id}/evidence/certificate", response_model=Section65BCertificate)
async def get_section_65b_certificate(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Section65BCertificate:
    """
    Generates formal Electronic Evidence Certificate pursuant to Section 63 of
    Bharatiya Sakshya Adhiniyam, 2023 / Section 65B of Indian Evidence Act, 1872 (E4-04).
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
            detail="You do not have permission to generate certificate for this inspection",
        )

    audit_stmt = select(AuditLog).order_by(AuditLog.created_at.asc())
    audit_res = await db.execute(audit_stmt)
    all_logs = audit_res.scalars().all()

    field_ids = {str(f.id) for f in inspection.fields}
    relevant_logs = [
        log for log in all_logs
        if (log.entity_type == "inspection" and log.entity_id == str(inspection.id))
        or (log.entity_type == "extracted_field" and log.entity_id in field_ids)
    ]

    service = EvidenceVerificationService()
    verification = service.verify_evidence_chain(inspection=inspection, audit_logs=relevant_logs)
    officer = inspection.officer or current_user
    return service.generate_section_65b_certificate(
        inspection=inspection,
        officer=officer,
        verification=verification,
    )


@router.get("/{inspection_id}/review-queue", response_model=InspectionReviewQueueResponse)
async def get_inspection_review_queue(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> InspectionReviewQueueResponse:
    """
    Retrieve declarations routed to human review queue (REV-01).
    Surfaces low-confidence detections (< 85%), format ambiguities, and uncalibrated readings.
    """
    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
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
            detail="You do not have permission to view review queue for this inspection",
        )

    img_map = {img.id: img for img in inspection.images}
    front_img = next((img for img in inspection.images if img.image_role == "front_pdp"), None)
    if front_img is None and len(inspection.images) > 0:
        front_img = inspection.images[0]

    field_violations: dict[uuid.UUID, list[ViolationRead]] = {}
    for v in inspection.violations:
        if v.extracted_field_id:
            field_violations.setdefault(v.extracted_field_id, []).append(
                ViolationRead(
                    id=v.id,
                    inspection_id=v.inspection_id,
                    extracted_field_id=v.extracted_field_id,
                    rule_id=v.rule_id,
                    rule_pack_version=v.rule_pack_version,
                    description=v.description,
                    citation=v.citation,
                    severity=v.severity,
                    created_at=v.created_at,
                )
            )

    review_items: list[ReviewQueueItemRead] = []
    pending_count = 0
    completed_count = 0

    for f in inspection.fields:
        field_thresh = get_field_confidence_threshold(f.field_type)
        is_reviewed = bool(f.reviewed_by_officer)
        if is_reviewed:
            completed_count += 1
        elif f.verdict == "needs_review" or float(f.confidence) < field_thresh:
            pending_count += 1

        # Determine flag reason
        flag_reason = None
        if float(f.confidence) < field_thresh:
            flag_reason = f"Low extraction confidence ({float(f.confidence):.0%} < {field_thresh:.0%})"
        elif f.verdict == "needs_review":
            flag_reason = "Format or statutory qualifier ambiguity"
        elif is_reviewed:
            flag_reason = "Officer reviewed"
        else:
            flag_reason = "Automated check verified"

        src_img = img_map.get(f.source_image_id, front_img)
        display_url = ""
        if src_img:
            if src_img.storage_url.startswith("local://"):
                display_url = f"/api/v1/inspections/{inspection.id}/images/{src_img.id}/file"
            elif src_img.storage_url.startswith("/uploads/"):
                display_url = src_img.storage_url
            else:
                display_url = generate_presigned_download_url(src_img.storage_url)

        v_list = field_violations.get(f.id, [])
        label = FIELD_LABELS.get(f.field_type, f.field_type.replace("_", " ").upper())

        review_items.append(
            ReviewQueueItemRead(
                field_id=f.id,
                inspection_id=f.inspection_id,
                field_type=f.field_type,
                field_label=label,
                raw_text=f.raw_text,
                parsed_value=f.parsed_value,
                confidence=float(f.confidence),
                verdict=f.verdict,
                bounding_box=f.bounding_box or {},
                source_image_id=f.source_image_id,
                source_image_url=display_url,
                flag_reason=flag_reason,
                reviewed_by_officer=is_reviewed,
                officer_override_value=f.officer_override_value,
                violations=v_list,
            )
        )

    return InspectionReviewQueueResponse(
        inspection_id=inspection.id,
        overall_status=inspection.status,
        total_fields=len(inspection.fields),
        pending_review_count=pending_count,
        completed_review_count=completed_count,
        items=review_items,
    )


@router.patch("/{inspection_id}/fields/{field_id}", response_model=FieldReviewResponse)
async def review_and_override_field(
    inspection_id: uuid.UUID,
    field_id: uuid.UUID,
    payload: FieldReviewUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> FieldReviewResponse:
    """
    Human review endpoint for confirming, correcting, or marking an extracted field as not applicable (REV-02).
    Writes an immutable entry to audit_logs table (REV-03) and triggers automatic rule re-evaluation.
    """
    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
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
            detail="You do not have permission to review fields for this inspection",
        )

    target_field = next((f for f in inspection.fields if f.id == field_id), None)
    if target_field is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field {field_id} not found in inspection {inspection_id}",
        )

    if payload.action == "correct" and (
        not payload.officer_override_value or not payload.officer_override_value.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="officer_override_value is required when action is 'correct'",
        )

    # Capture before_value for immutable audit trail (REV-03)
    before_val = {
        "raw_text": target_field.raw_text,
        "parsed_value": target_field.parsed_value,
        "confidence": float(target_field.confidence),
        "verdict": target_field.verdict,
        "reviewed_by_officer": target_field.reviewed_by_officer,
        "officer_override_value": target_field.officer_override_value,
    }

    # Apply officer decision (REV-02)
    target_field.reviewed_by_officer = True
    if payload.action == "confirm":
        target_field.verdict = "pass"
        msg = f"Declaration '{target_field.field_type}' confirmed by officer {current_user.full_name}."
    elif payload.action == "correct":
        target_field.verdict = "pass"
        target_field.officer_override_value = payload.officer_override_value.strip()
        msg = (
            f"Declaration '{target_field.field_type}' corrected by officer to '{target_field.officer_override_value}'."
        )
    elif payload.action == "mark_not_applicable":
        target_field.verdict = "not_applicable"
        target_field.officer_override_value = None
        msg = f"Declaration '{target_field.field_type}' marked not applicable by officer."
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {payload.action}",
        )

    after_val = {
        "raw_text": target_field.raw_text,
        "parsed_value": target_field.parsed_value,
        "confidence": float(target_field.confidence),
        "verdict": target_field.verdict,
        "reviewed_by_officer": target_field.reviewed_by_officer,
        "officer_override_value": target_field.officer_override_value,
        "action": payload.action,
        "review_notes": payload.review_notes,
    }

    # Persist immutable audit log entry (REV-03)
    audit_id = uuid.uuid4()
    audit_entry = AuditLog(
        id=audit_id,
        actor_user_id=current_user.id,
        action=f"field_{payload.action}",
        entity_type="extracted_field",
        entity_id=str(target_field.id),
        before_value=before_val,
        after_value=after_val,
    )
    db.add(audit_entry)

    # Automatically re-evaluate rules against frozen rule pack version
    pack_stmt = select(RulePack).where(RulePack.version == inspection.rule_pack_version)
    pack_res = await db.execute(pack_stmt)
    rule_pack = pack_res.scalar_one_or_none()

    rule_engine = RuleEngine()
    summary = rule_engine.evaluate_rules(
        fields=inspection.fields,
        images=inspection.images,
        commodity_category=inspection.commodity_category,
        rule_pack=rule_pack or rule_engine.default_pack,
    )

    # Repopulate violations table
    await db.execute(delete(Violation).where(Violation.inspection_id == inspection.id))
    for v in summary.violations:
        violation = Violation(
            id=uuid.uuid4(),
            inspection_id=inspection.id,
            extracted_field_id=v["extracted_field_id"],
            rule_id=v["rule_id"],
            rule_pack_version=v["rule_pack_version"],
            description=v["description"],
            citation=v["citation"],
            severity=v["severity"],
        )
        db.add(violation)

    # Determine overall inspection status: if any unreviewed fields still need review, stays needs_review
    has_unreviewed_pending = any(
        not f.reviewed_by_officer
        and (f.verdict == "needs_review" or float(f.confidence) < get_field_confidence_threshold(f.field_type))
        for f in inspection.fields
    )

    if has_unreviewed_pending or summary.overall_status == "needs_review":
        inspection.status = "needs_review"
    else:
        inspection.status = "completed"

    await db.commit()
    await db.refresh(target_field)
    await db.refresh(inspection)

    return FieldReviewResponse(
        field=ExtractedFieldRead.model_validate(target_field),
        inspection_status=inspection.status,
        violations_count=len(summary.violations),
        audit_log_id=audit_id,
        message=msg,
    )


@router.get("/{inspection_id}/audit-logs", response_model=list[AuditLogRead])
async def get_inspection_audit_logs(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[AuditLog]:
    """
    Retrieve the immutable audit trail for an inspection and its associated declarations (REV-03).
    Ensures complete chain-of-custody transparency for all human review overrides.
    """
    stmt = select(Inspection).where(Inspection.id == inspection_id).options(selectinload(Inspection.fields))
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
            detail="You do not have permission to view audit logs for this inspection",
        )

    field_id_strs = [str(f.id) for f in inspection.fields]
    entity_ids = [str(inspection.id)] + field_id_strs

    audit_stmt = select(AuditLog).where(AuditLog.entity_id.in_(entity_ids)).order_by(AuditLog.created_at.desc())
    audit_res = await db.execute(audit_stmt)
    return list(audit_res.scalars().all())


@router.post("/{inspection_id}/fields/batch-review", response_model=BatchFieldReviewResponse)
async def batch_review_fields(
    inspection_id: uuid.UUID,
    payload: BatchFieldReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BatchFieldReviewResponse:
    """
    Batch human review endpoint for confirming, correcting, or marking multiple extracted fields
    in a single atomic transaction (E2-04).
    Writes immutable entries to audit_logs and triggers automatic rule re-evaluation.
    """
    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
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
            detail="You do not have permission to review fields for this inspection",
        )

    field_map = {f.id: f for f in inspection.fields}
    audit_ids: list[uuid.UUID] = []
    updated_fields: list[ExtractedField] = []

    now = datetime.now(timezone.utc)

    for item in payload.items:
        target_field = field_map.get(item.field_id)
        if target_field is None:
            continue

        before_state = {
            "parsed_value": target_field.parsed_value,
            "verdict": target_field.verdict,
            "reviewed_by_officer": target_field.reviewed_by_officer,
            "officer_override_value": target_field.officer_override_value,
        }

        target_field.reviewed_by_officer = True

        if item.action == "confirm":
            target_field.verdict = "pass"
            target_field.officer_override_value = None
            action_name = "CONFIRM_DECLARATION"
        elif item.action == "override":
            target_field.officer_override_value = item.officer_override_value
            target_field.verdict = "pass"
            action_name = "OVERRIDE_DECLARATION"
        elif item.action == "mark_not_applicable":
            target_field.verdict = "not_applicable"
            target_field.officer_override_value = None
            action_name = "MARK_NOT_APPLICABLE"

        after_state = {
            "parsed_value": target_field.parsed_value,
            "verdict": target_field.verdict,
            "reviewed_by_officer": target_field.reviewed_by_officer,
            "officer_override_value": target_field.officer_override_value,
            "officer_notes": item.officer_notes,
            "reviewed_at": now.isoformat(),
            "reviewed_by": str(current_user.id),
        }

        audit_id = uuid.uuid4()
        audit_entry = AuditLog(
            id=audit_id,
            actor_user_id=current_user.id,
            action=action_name,
            entity_type="extracted_field",
            entity_id=str(target_field.id),
            before_value=before_state,
            after_value=after_state,
            created_at=now,
        )
        db.add(audit_entry)
        audit_ids.append(audit_id)
        updated_fields.append(target_field)

    # Re-evaluate rules after batch update
    rule_pack_stmt = select(RulePack).where(RulePack.version == inspection.rule_pack_version)
    rp_res = await db.execute(rule_pack_stmt)
    rule_pack = rp_res.scalar_one_or_none()

    rule_engine = RuleEngine()
    summary = rule_engine.evaluate_rules(
        fields=inspection.fields,
        images=inspection.images,
        commodity_category=inspection.commodity_category,
        rule_pack=rule_pack or rule_engine.default_pack,
    )

    # Update violations table
    await db.execute(delete(Violation).where(Violation.inspection_id == inspection.id))
    for v in summary.violations:
        violation = Violation(
            id=uuid.uuid4(),
            inspection_id=inspection.id,
            extracted_field_id=v["extracted_field_id"],
            rule_id=v["rule_id"],
            rule_pack_version=v["rule_pack_version"],
            description=v["description"],
            citation=v["citation"],
            severity=v["severity"],
        )
        db.add(violation)

    # Recalculate status
    has_unreviewed_pending = any(
        not f.reviewed_by_officer
        and (f.verdict == "needs_review" or float(f.confidence) < get_field_confidence_threshold(f.field_type))
        for f in inspection.fields
    )

    if has_unreviewed_pending or summary.overall_status == "needs_review":
        inspection.status = "needs_review"
    else:
        inspection.status = "completed"

    await db.commit()
    await db.refresh(inspection)

    return BatchFieldReviewResponse(
        inspection_id=inspection.id,
        inspection_status=inspection.status,
        reviewed_count=len(updated_fields),
        violations_count=len(summary.violations),
        updated_fields=[ExtractedFieldRead.model_validate(f) for f in updated_fields],
        audit_log_ids=audit_ids,
        message=f"Successfully batch-reviewed {len(updated_fields)} declarations.",
    )


@router.get("/{inspection_id}/review-history")
async def get_inspection_review_history(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    """
    Retrieve enriched review audit history for an inspection with officer details (E2-04).
    """
    stmt = select(Inspection).where(Inspection.id == inspection_id).options(selectinload(Inspection.fields))
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
            detail="You do not have permission to view review history for this inspection",
        )

    field_map = {str(f.id): f.field_type for f in inspection.fields}
    field_id_strs = list(field_map.keys())
    entity_ids = [str(inspection.id)] + field_id_strs

    audit_stmt = (
        select(AuditLog, User.full_name, User.role)
        .join(User, AuditLog.actor_user_id == User.id)
        .where(AuditLog.entity_id.in_(entity_ids))
        .order_by(AuditLog.created_at.desc())
    )
    audit_res = await db.execute(audit_stmt)
    rows = audit_res.all()

    history = []
    for log, officer_name, officer_role in rows:
        field_type = field_map.get(log.entity_id, "inspection")
        history.append(
            {
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "field_type": field_type,
                "officer_id": log.actor_user_id,
                "officer_name": officer_name,
                "officer_role": officer_role,
                "before_value": log.before_value,
                "after_value": log.after_value,
                "created_at": log.created_at,
            }
        )

    return history


@router.post(
    "/{inspection_id}/report",
    response_model=ReportRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an inspection compliance report (PDF or editable JSON)",
)
async def generate_inspection_report(
    inspection_id: uuid.UUID,
    payload: ReportGenerateRequest | None = None,
    format: ReportFormatType = "pdf",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ReportRead:
    """
    Generates a formal Legal Metrology compliance report (RPT-01, RPT-02, RPT-03, RPT-04).
    Embeds mandatory statutory disclaimer, declaration findings, violations, and audit history.
    Stores report in Cloudflare R2 (production) or local uploads (offline/development).
    """
    effective_format = payload.format if (payload and payload.format) else format

    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.images),
            selectinload(Inspection.fields),
            selectinload(Inspection.violations),
        )
    )
    res = await db.execute(stmt)
    inspection = res.scalar_one_or_none()

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection {inspection_id} not found",
        )

    # RBAC: inspecting officer, supervisor, or admin
    if inspection.officer_id != current_user.id and current_user.role not in ["supervisor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to generate reports for this inspection",
        )

    # Fetch audit logs for the inspection
    field_id_strs = [str(f.id) for f in inspection.fields]
    entity_ids = [str(inspection.id)] + field_id_strs
    audit_stmt = select(AuditLog).where(AuditLog.entity_id.in_(entity_ids)).order_by(AuditLog.created_at.asc())
    audit_res = await db.execute(audit_stmt)
    audit_logs = list(audit_res.scalars().all())

    # Fetch officer info
    officer_stmt = select(User).where(User.id == inspection.officer_id)
    officer_res = await db.execute(officer_stmt)
    officer = officer_res.scalar_one_or_none() or current_user

    report_service = ReportService()
    context = {
        "inspection": inspection,
        "officer": officer,
        "images": inspection.images,
        "fields": inspection.fields,
        "violations": inspection.violations,
        "audit_logs": audit_logs,
        "generated_at_str": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    report_id = uuid.uuid4()
    insp_str = str(inspection.id)
    rep_str = str(report_id)
    if effective_format == "editable":
        file_bytes = report_service.generate_editable_export(context)
        filename = f"report_{insp_str[:8]}_{rep_str[:8]}.json"
        content_type = "application/json"
    else:
        file_bytes, _ = report_service.generate_pdf(context)
        filename = f"report_{insp_str[:8]}_{rep_str[:8]}.pdf"
        content_type = "application/pdf"

    storage_url = await save_report_bytes(
        inspection_id=inspection.id,
        report_id=report_id,
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
    )

    # Save to database
    report = Report(
        id=report_id,
        inspection_id=inspection.id,
        format=effective_format,
        storage_url=storage_url,
        generated_by=current_user.id,
    )
    db.add(report)

    # Record immutable audit log
    audit_log = AuditLog(
        actor_user_id=current_user.id,
        action="report_generated",
        entity_type="report",
        entity_id=str(report_id),
        before_value=None,
        after_value={
            "format": format,
            "filename": filename,
            "storage_url": storage_url,
        },
    )
    db.add(audit_log)
    await db.commit()
    await db.refresh(report)

    download_url = f"/api/v1/inspections/{inspection_id}/reports/{report_id}/file"

    return ReportRead(
        id=report.id,
        inspection_id=report.inspection_id,
        format=report.format,
        storage_url=report.storage_url,
        download_url=download_url,
        generated_by=report.generated_by,
        generated_at=report.generated_at,
    )


@router.get(
    "/{inspection_id}/reports",
    response_model=list[ReportRead],
    summary="List all reports generated for an inspection",
)
async def list_inspection_reports(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ReportRead]:
    """Lists all generated compliance reports for an inspection."""
    stmt = select(Report).where(Report.inspection_id == inspection_id).order_by(Report.generated_at.desc())
    res = await db.execute(stmt)
    reports = res.scalars().all()

    return [
        ReportRead(
            id=r.id,
            inspection_id=r.inspection_id,
            format=r.format,
            storage_url=r.storage_url,
            download_url=f"/api/v1/inspections/{inspection_id}/reports/{r.id}/file",
            generated_by=r.generated_by,
            generated_at=r.generated_at,
        )
        for r in reports
    ]


@router.get(
    "/{inspection_id}/reports/{report_id}/file",
    summary="Download the generated report file",
)
async def download_report_file(
    inspection_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Downloads/streams the generated report file (PDF or JSON)."""
    stmt = select(Report).where(
        Report.id == report_id,
        Report.inspection_id == inspection_id,
    )
    res = await db.execute(stmt)
    report = res.scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found for inspection {inspection_id}",
        )

    # Check local filesystem
    local_rel = report.storage_url.lstrip("/")
    if local_rel.startswith("uploads/"):
        file_path = Path(".") / local_rel
    else:
        file_path = Path(f"./uploads/{inspection_id}/reports")

    # Look for matching file in uploads/{inspection_id}/reports
    if not (file_path.exists() and file_path.is_file()):
        report_dir = Path(f"./uploads/{inspection_id}/reports")
        candidates = list(report_dir.glob(f"*{str(report_id)[:8]}*")) if report_dir.exists() else []
        if candidates:
            file_path = candidates[0]

    if file_path.exists() and file_path.is_file():
        media_type = "application/pdf" if report.format == "pdf" else "application/json"
        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=file_path.name,
        )

    # If Cloudflare R2 presigned/public URL, redirect
    if report.storage_url.startswith("http"):
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url=report.storage_url)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Report file is missing from storage",
    )
