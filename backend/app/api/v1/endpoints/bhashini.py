"""
Bhashini Multilingual Endpoints (E3-04, ADR-013).
Provides translation, speech synthesis, and vernacular voice UI for Legal Metrology officers.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user, get_db
from app.models.base import Inspection, User
from app.services.bhashini import (
    BhashiniService,
    InspectionTranslationResponse,
    SupportedLanguagesResponse,
    TranslationRequest,
    TranslationResponse,
    TTSRequest,
    TTSResponse,
)

router = APIRouter()


@router.get("/languages", response_model=SupportedLanguagesResponse)
async def get_supported_indic_languages() -> SupportedLanguagesResponse:
    """
    Returns the 12 supported Indian regional languages for translation and voice narration.
    """
    service = BhashiniService()
    return service.get_supported_languages()


@router.post("/translate", response_model=TranslationResponse)
async def translate_text(
    payload: TranslationRequest,
    current_user: User = Depends(get_current_active_user),
) -> TranslationResponse:
    """
    Translates text between English and 12 Indic regional languages.
    Environment-driven: queries Bhashini ULCA when configured, or uses offline dictionary.
    """
    service = BhashiniService()
    return await service.translate_text(
        text=payload.text,
        source_lang=payload.source_language,
        target_lang=payload.target_language,
    )


@router.post("/tts", response_model=TTSResponse)
async def synthesize_speech(
    payload: TTSRequest,
    current_user: User = Depends(get_current_active_user),
) -> TTSResponse:
    """
    Synthesizes text into spoken audio (base64).
    Uses Bhashini ULCA TTS when configured, or returns fallback audio payload for client Web Speech.
    """
    service = BhashiniService()
    return await service.synthesize_speech(
        text=payload.text,
        language=payload.language,
        gender=payload.gender,
    )


@router.post(
    "/inspections/{inspection_id}/translate",
    response_model=InspectionTranslationResponse,
)
async def translate_inspection_report(
    inspection_id: uuid.UUID,
    target_language: str = Query(default="hi", description="Target language code (e.g. 'hi', 'mr', 'ta')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> InspectionTranslationResponse:
    """
    Translates an entire inspection report (all declarations, violations, and statutory citations)
    into the officer's chosen Indic language, and generates a spoken narration summary.
    """
    stmt = (
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
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
            detail="You do not have permission to view this inspection",
        )

    service = BhashiniService()
    return await service.translate_inspection(inspection=inspection, target_lang=target_language)
