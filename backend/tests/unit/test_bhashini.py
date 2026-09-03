"""
Unit tests for Bhashini Multilingual Service (E3-04, ADR-013).
Verifies offline fallback, Indic dictionary translations, speech synthesis, and narration.
"""

import uuid
from datetime import datetime, timezone
import pytest

from app.models.base import ExtractedField, Inspection, Violation
from app.services.bhashini.service import BhashiniService


@pytest.mark.asyncio
async def test_bhashini_supported_languages():
    """Verify that Bhashini service returns 12 supported Indian regional languages."""
    service = BhashiniService()
    resp = service.get_supported_languages()

    assert resp.total == 12
    codes = [lang.code for lang in resp.languages]
    assert "hi" in codes  # Hindi
    assert "mr" in codes  # Marathi
    assert "gu" in codes  # Gujarati
    assert "bn" in codes  # Bengali
    assert "ta" in codes  # Tamil
    assert "te" in codes  # Telugu
    assert "en" in codes  # English

    hindi = next(l for l in resp.languages if l.code == "hi")
    assert hindi.script == "Devanagari"
    assert hindi.native_name == "हिन्दी"


@pytest.mark.asyncio
async def test_bhashini_offline_translation_dictionary():
    """Verify offline dictionary translation for Legal Metrology mandatory declarations."""
    service = BhashiniService()

    # Translate MRP to Hindi
    resp_hi = await service.translate_text("mrp", "en", "hi")
    assert "अधिकतम खुदरा मूल्य" in resp_hi.translated_text
    assert resp_hi.is_offline_fallback is True

    # Translate Net Quantity to Marathi
    resp_mr = await service.translate_text("net_quantity", "en", "mr")
    assert "निव्वळ प्रमाण" in resp_mr.translated_mr if hasattr(resp_mr, "translated_mr") else "निव्वळ प्रमाण" in resp_mr.translated_text
    assert resp_mr.is_offline_fallback is True

    # Translate statutory violation phrase
    resp_inf = await service.translate_text("E-commerce listing price exceeds package MRP", "en", "hi")
    assert "अधिक मूल्य" in resp_inf.translated_text


@pytest.mark.asyncio
async def test_bhashini_speech_synthesis_fallback():
    """Verify TTS speech synthesis returns playable audio payload with offline indicator."""
    service = BhashiniService()
    resp = await service.synthesize_speech("निरीक्षण पास हुआ", language="hi", gender="female")

    assert resp.language == "hi"
    assert resp.audio_format == "wav"
    assert len(resp.audio_content_base64) > 10
    assert resp.is_offline_fallback is True


@pytest.mark.asyncio
async def test_bhashini_inspection_translation_and_narration():
    """Verify full inspection report translation and spoken audio narration generation."""
    service = BhashiniService()
    insp_id = uuid.uuid4()
    officer_id = uuid.uuid4()

    inspection = Inspection(
        id=insp_id,
        officer_id=officer_id,
        commodity_category="packaged_food",
        status="needs_review",
        rule_pack_version="2026.02.01",
        created_at=datetime.now(timezone.utc),
    )

    f_mrp = ExtractedField(
        id=uuid.uuid4(),
        inspection_id=insp_id,
        source_image_id=uuid.uuid4(),
        field_type="mrp",
        raw_text="MRP Rs. 150.00",
        parsed_value="Rs. 150.00",
        confidence=0.92,
        bounding_box={"x": 10, "y": 10, "w": 50, "h": 20},
        verdict="pass",
    )
    f_qty = ExtractedField(
        id=uuid.uuid4(),
        inspection_id=insp_id,
        source_image_id=uuid.uuid4(),
        field_type="net_quantity",
        raw_text="500 g",
        parsed_value="500 g",
        confidence=0.88,
        bounding_box={"x": 10, "y": 35, "w": 50, "h": 20},
        verdict="pass",
    )
    inspection.fields = [f_mrp, f_qty]

    v1 = Violation(
        id=uuid.uuid4(),
        inspection_id=insp_id,
        extracted_field_id=f_mrp.id,
        rule_id="cross-match-ecommerce-mrp-inflation",
        rule_pack_version="2026.02.01",
        description="E-commerce listing price exceeds package MRP",
        citation="LM(PC) Rules 2011, Rule 6(10) & Rule 18(2)",
        severity="critical",
    )
    inspection.violations = [v1]

    report = await service.translate_inspection(inspection, target_lang="hi")

    assert report.inspection_id == insp_id
    assert report.target_language == "hi"
    assert report.target_language_name == "हिन्दी"
    assert len(report.fields) == 2
    assert len(report.violations) == 1

    # Check Hindi field labels
    mrp_field = next(f for f in report.fields if f.field_type == "mrp")
    assert "अधिकतम खुदरा मूल्य" in mrp_field.label

    # Check voice narration text
    assert "निरीक्षण परिणाम:" in report.summary_narration
    assert "1 उल्लंघन पाए गए" in report.summary_narration
