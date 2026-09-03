"""
Pydantic schemas for Bhashini ULCA Multilingual Integration (E3-04, ADR-013).
Supports translation (NMT), text-to-speech (TTS), and vernacular voice narration.
"""

from typing import Any, Optional
import uuid
from pydantic import BaseModel, Field


class SupportedLanguage(BaseModel):
    code: str = Field(..., description="ISO 639-1 / Bhashini language code (e.g., 'hi', 'mr', 'ta')")
    name: str = Field(..., description="English display name (e.g., 'Hindi', 'Marathi')")
    native_name: str = Field(..., description="Native language script name (e.g., 'हिन्दी', 'मराठी')")
    script: str = Field(..., description="Primary writing script (e.g., 'Devanagari', 'Tamil')")


class SupportedLanguagesResponse(BaseModel):
    total: int
    languages: list[SupportedLanguage]


class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Source text to translate")
    source_language: str = Field(default="en", description="Source language code (default 'en')")
    target_language: str = Field(default="hi", description="Target Indic language code (default 'hi')")


class TranslationResponse(BaseModel):
    source_language: str
    target_language: str
    source_text: str
    translated_text: str
    is_offline_fallback: bool = Field(
        ..., description="True if local offline dictionary/transliteration was used"
    )


class BatchTranslationRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, description="List of source strings to translate")
    source_language: str = Field(default="en", description="Source language code")
    target_language: str = Field(default="hi", description="Target Indic language code")


class BatchTranslationResponse(BaseModel):
    source_language: str
    target_language: str
    translations: list[str]
    is_offline_fallback: bool


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to synthesize to speech")
    language: str = Field(default="hi", description="Indic language code (e.g., 'hi', 'mr', 'ta')")
    gender: str = Field(default="female", description="Voice gender: female | male")


class TTSResponse(BaseModel):
    language: str
    audio_format: str = "wav"
    audio_content_base64: str = Field(..., description="Base64-encoded audio bytes or synthetic tone")
    is_offline_fallback: bool


class InspectionFieldTranslation(BaseModel):
    field_id: uuid.UUID
    field_type: str
    label: str
    original_value: str
    translated_value: str


class InspectionViolationTranslation(BaseModel):
    violation_id: uuid.UUID
    rule_id: str
    severity: str
    original_description: str
    translated_description: str
    citation: str


class InspectionTranslationResponse(BaseModel):
    inspection_id: uuid.UUID
    target_language: str
    target_language_name: str
    is_offline_fallback: bool
    summary_narration: str = Field(
        ..., description="Complete vernacular spoken narration for voice readout"
    )
    fields: list[InspectionFieldTranslation]
    violations: list[InspectionViolationTranslation]
