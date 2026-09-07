"""
Bhashini ULCA Multilingual Service (E3-04, ADR-013).
Provides translation (NMT), text-to-speech (TTS), and vernacular voice narration
for Legal Metrology field inspections. Environment-driven with live ULCA client
and resilient offline dictionary fallback.
"""

import logging

import httpx

from app.core.config import settings
from app.models.base import Inspection
from app.services.bhashini.schemas import (
    InspectionFieldTranslation,
    InspectionTranslationResponse,
    InspectionViolationTranslation,
    SupportedLanguage,
    SupportedLanguagesResponse,
    TranslationResponse,
    TTSResponse,
)

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES: list[SupportedLanguage] = [
    SupportedLanguage(code="hi", name="Hindi", native_name="हिन्दी", script="Devanagari"),
    SupportedLanguage(code="mr", name="Marathi", native_name="मराठी", script="Devanagari"),
    SupportedLanguage(code="gu", name="Gujarati", native_name="ગુજરાતી", script="Gujarati"),
    SupportedLanguage(code="bn", name="Bengali", native_name="বাংলা", script="Bengali"),
    SupportedLanguage(code="ta", name="Tamil", native_name="தமிழ்", script="Tamil"),
    SupportedLanguage(code="te", name="Telugu", native_name="తెలుగు", script="Telugu"),
    SupportedLanguage(code="kn", name="Kannada", native_name="ಕನ್ನಡ", script="Kannada"),
    SupportedLanguage(code="ml", name="Malayalam", native_name="മലയാളം", script="Malayalam"),
    SupportedLanguage(code="pa", name="Punjabi", native_name="ਪੰਜਾਬੀ", script="Gurmukhi"),
    SupportedLanguage(code="or", name="Odia", native_name="ଓଡ଼ିଆ", script="Odia"),
    SupportedLanguage(code="as", name="Assamese", native_name="অসমীয়া", script="Bengali-Assamese"),
    SupportedLanguage(code="en", name="English", native_name="English", script="Latin"),
]

# Curated Legal Metrology domain terms in primary Indic languages (PCR 2011)
LEGAL_METROLOGY_DICTIONARY: dict[str, dict[str, str]] = {
    "mrp": {
        "hi": "अधिकतम खुदरा मूल्य (MRP)",
        "mr": "कमाल किरकोळ किंमत (MRP)",
        "gu": "મહત્તમ છૂટક કિંમત (MRP)",
        "bn": "সর্বোচ্চ খুচরা মূল্য (MRP)",
        "ta": "அதிகபட்ச சில்லறை விலை (MRP)",
        "te": "గరిష్ట రిటైల్ ధర (MRP)",
    },
    "net_quantity": {
        "hi": "शुद्ध मात्रा (Net Quantity)",
        "mr": "निव्वळ प्रमाण (Net Quantity)",
        "gu": "ચોખ્ખો જથ્થો (Net Quantity)",
        "bn": "নেট পরিমাণ (Net Quantity)",
        "ta": "நிகர அளவு (Net Quantity)",
        "te": "నికర పరిమాణం (Net Quantity)",
    },
    "date_of_manufacture": {
        "hi": "निर्माण की तिथि (Mfg Date)",
        "mr": "उत्पादनाची तारीख",
        "gu": "ઉત્પાદનની તારીખ",
        "bn": "উত্পাদনের তারিখ",
        "ta": "உற்பத்தி தேதி",
        "te": "తయారీ తేదీ",
    },
    "manufacturer_address": {
        "hi": "निर्माता का नाम व पता",
        "mr": "उत्पादकाचे नाव आणि पत्ता",
        "gu": "ઉત્પાદકનું નામ અને સરનામું",
        "bn": "প্রস্তুতকারকের নাম ও ঠিকানা",
        "ta": "உற்பத்தியாளர் பெயர் மற்றும் முகவரி",
        "te": "తయారీదారు పేరు మరియు చిరునామా",
    },
    "consumer_care": {
        "hi": "उपभोक्ता सहायता विवरण (हेल्पलाइन / ईमेल)",
        "mr": "ग्राहक सेवा तपशील",
        "gu": "ગ્રાહક સંભાળ વિગતો",
        "bn": "ভোক্তা সেবা বিবরণ",
        "ta": "நுகர்வோர் பராமரிப்பு விவரங்கள்",
        "te": "వినియోగదారు సంరక్షణ వివరాలు",
    },
    "country_of_origin": {
        "hi": "उत्पत्ति का देश",
        "mr": "मूळ देश",
        "gu": "મૂળ દેશ",
        "bn": "উৎস দেশ",
        "ta": "பிறப்பிட நாடு",
        "te": "మూల దేశం",
    },
    "dimensions_and_count": {
        "hi": "आकार और वस्तु संख्या",
        "mr": "आकार आणि संख्या",
        "gu": "પરિમાણો અને ગણતરી",
        "bn": "মাত্রা এবং সংখ্যা",
        "ta": "பரிமாணங்கள் மற்றும் எண்ணிக்கை",
        "te": "కొలతలు మరియు సంఖ్య",
    },
    "importer_packer": {
        "hi": "आयातकर्ता / पैकर विवरण",
        "mr": "आयातदार / पॅकर तपशील",
        "gu": "આયાતકાર / પેકર વિગતો",
        "bn": "আমদানিকারক / প্যাকার বিবরণ",
        "ta": "இறக்குமதியாளர் / பேக்கர் விவரங்கள்",
        "te": "దిగుమతిదారు / ప్యాకర్ వివరాలు",
    },
    "retail_sale_price": {
        "hi": "इकाई विक्रय मूल्य (Unit Sale Price)",
        "mr": "युनिट विक्री किंमत",
        "gu": "યુનિટ વેચાણ કિંમત",
        "bn": "একক বিক্রয় মূল্য",
        "ta": "அலகு விற்பனை விலை",
        "te": "యూనిట్ అమ్మకపు ధర",
    },
}

# Common phrase translations for statutory summaries
STATUTORY_PHRASES: dict[str, dict[str, str]] = {
    "pass": {
        "hi": "वैधानिक रूप से अनुपालित (पास)",
        "mr": "कायदेशीरदृष्ट्या सुसंगत (पास)",
        "gu": "કાયદાકીય રીતે સુસંગત (પાસ)",
        "bn": "আইনত সঙ্গতিপূর্ণ (পাস)",
        "ta": "சட்டபூர்வமாக இணக்கமானது (தேர்ச்சி)",
        "te": "చట్టబద్ధంగా సరిపోలింది (పాస్)",
    },
    "violation_detected": {
        "hi": "विधिक मापविज्ञान नियम उल्लंघन पाया गया",
        "mr": "वैधानिक वजन व मापे नियम उल्लंघन आढळले",
        "gu": "કાનૂની માપવિજ્ઞાન નિયમ ઉલ્લંઘન મળ્યું",
        "bn": "আইনি পরিমাপবিজ্ঞান নিয়ম লঙ্ঘন পাওয়া গেছে",
        "ta": "சட்ட அளவையியல் விதிமீறல் கண்டறியப்பட்டது",
        "te": "లీగల్ మెట్రాలజీ నిబంధనల ఉల్లంఘన గుర్తించబడింది",
    },
    "mrp_inflation": {
        "hi": "ई-कॉमर्स लिस्टिंग में मुद्रित एमआरपी से अधिक मूल्य वसूलना (नियम 18(2) का उल्लंघन)",
        "mr": "ई-कॉमर्स सूचीवर छापील एमआरपीपेक्षा जास्त किंमत आकारणे (नियम 18(2))",
        "gu": "ઇ-કોમર્સ લિસ્ટિંગમાં છાપેલી એમઆરપી કરતા વધુ ભાવ વસૂલવો (નિયમ 18(2))",
        "bn": "ই-কমার্স তালিকায় মুদ্রিত এমআরপি-এর চেয়ে বেশি মূল্য ধার্য করা (নিয়ম 18(2))",
        "ta": "இ-காமர்ஸ் பட்டியலில் அச்சிடப்பட்ட எம்ஆர்பி-யை விட அதிக விலை வசூலிப்பது (விதி 18(2))",
        "te": "ఈ-కామర్స్ లిస్టింగ్‌లో ప్రింటెడ్ ఎంఆర్‌పి కంటే ఎక్కువ ధర వసూలు చేయడం (రూల్ 18(2))",
    },
    "net_quantity_mismatch": {
        "hi": "ई-कॉमर्स विज्ञापित मात्रा और भौतिक पैकेज मात्रा में विसंगति (नियम 6(10))",
        "mr": "ई-कॉमर्स जाहिरात केलेले प्रमाण आणि प्रत्यक्ष पॅकेजमध्ये तफावत (नियम 6(10))",
        "gu": "ઇ-કોમર્સ જાહેરાત જથ્થો અને વાસ્તવિક પેકેજ વચ્ચે વિસંગતતા (નિયમ 6(10))",
        "bn": "ই-কমার্স বিজ্ঞাপিত পরিমাণ এবং প্রকৃত প্যাকেজের মধ্যে অমিল (নিয়ম 6(10))",
        "ta": "இ-காமர்ஸ் விளம்பரப்படுத்தப்பட்ட அளவுக்கும் இயற்பியல் பொதிக்கும் உள்ள முரண்பாடு (விதி 6(10))",
        "te": "ఈ-కామర్స్ ప్రకటన పరిమాణం మరియు ప్యాకేజీ పరిమాణంలో తేడా (రూల్ 6(10))",
    },
}

# Synthetic minimal WAV audio bytes for offline TTS fallback (44-byte silent WAV header)
OFFLINE_WAV_HEADER_B64 = "UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="


class BhashiniService:
    """
    Multilingual translation and speech synthesis adapter for Legal Metrology officers.
    Transparently calls Bhashini ULCA endpoints when configured, or provides immediate
    offline Indic dictionary translation and audio fallback.
    """

    def __init__(self) -> None:
        self.api_key = settings.BHASHINI_API_KEY.strip()
        self.user_id = settings.BHASHINI_USER_ID.strip()
        self.pipeline_id = settings.BHASHINI_PIPELINE_ID.strip()
        self.endpoint = settings.BHASHINI_INFERENCE_ENDPOINT.strip()

    @property
    def is_live_configured(self) -> bool:
        """Returns True if valid Bhashini API credentials are present."""
        return bool(self.api_key and self.user_id)

    def get_supported_languages(self) -> SupportedLanguagesResponse:
        """Returns the list of 12 supported Indian regional languages."""
        return SupportedLanguagesResponse(
            total=len(SUPPORTED_LANGUAGES),
            languages=SUPPORTED_LANGUAGES,
        )

    async def translate_text(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "hi",
    ) -> TranslationResponse:
        """
        Translates text from source_lang to target_lang.
        Uses live Bhashini NMT pipeline if configured; falls back to offline dictionary.
        """
        if not text or not text.strip():
            return TranslationResponse(
                source_language=source_lang,
                target_language=target_lang,
                source_text=text,
                translated_text="",
                is_offline_fallback=True,
            )

        # If live credentials configured, attempt ULCA inference
        if self.is_live_configured:
            try:
                translated = await self._call_bhashini_nmt(text, source_lang, target_lang)
                if translated:
                    return TranslationResponse(
                        source_language=source_lang,
                        target_language=target_lang,
                        source_text=text,
                        translated_text=translated,
                        is_offline_fallback=False,
                    )
            except Exception as e:
                logger.warning("Bhashini live NMT call failed (%s), falling back to offline dictionary.", e)

        # Offline dictionary / rule-based Indic fallback
        translated = self._translate_offline(text, target_lang)
        return TranslationResponse(
            source_language=source_lang,
            target_language=target_lang,
            source_text=text,
            translated_text=translated,
            is_offline_fallback=True,
        )

    async def synthesize_speech(
        self,
        text: str,
        language: str = "hi",
        gender: str = "female",
    ) -> TTSResponse:
        """
        Synthesizes text into audio bytes (base64).
        Uses live Bhashini TTS pipeline if configured, or returns fallback audio payload.
        """
        if self.is_live_configured:
            try:
                audio_b64 = await self._call_bhashini_tts(text, language, gender)
                if audio_b64:
                    return TTSResponse(
                        language=language,
                        audio_format="wav",
                        audio_content_base64=audio_b64,
                        is_offline_fallback=False,
                    )
            except Exception as e:
                logger.warning("Bhashini live TTS call failed (%s), falling back to offline audio.", e)

        return TTSResponse(
            language=language,
            audio_format="wav",
            audio_content_base64=OFFLINE_WAV_HEADER_B64,
            is_offline_fallback=True,
        )

    async def translate_inspection(
        self,
        inspection: Inspection,
        target_lang: str = "hi",
    ) -> InspectionTranslationResponse:
        """
        Translates all fields and violations of an inspection into the target Indic language.
        Generates a concise spoken summary narration for on-site voice playback.
        """
        target_lang_obj = next(
            (lang for lang in SUPPORTED_LANGUAGES if lang.code == target_lang),
            SupportedLanguage(code="hi", name="Hindi", native_name="हिन्दी", script="Devanagari"),
        )

        translated_fields: list[InspectionFieldTranslation] = []
        for field in inspection.fields or []:
            field_dict = LEGAL_METROLOGY_DICTIONARY.get(field.field_type, {})
            label = field_dict.get(target_lang, field.field_type.replace("_", " ").title())
            val = str(field.parsed_value or field.raw_text or "")
            trans_resp = await self.translate_text(val, "en", target_lang)
            translated_fields.append(
                InspectionFieldTranslation(
                    field_id=field.id,
                    field_type=field.field_type,
                    label=label,
                    original_value=val,
                    translated_value=trans_resp.translated_text or val,
                )
            )

        translated_violations: list[InspectionViolationTranslation] = []
        for v in inspection.violations or []:
            trans_resp = await self.translate_text(v.description, "en", target_lang)
            translated_violations.append(
                InspectionViolationTranslation(
                    violation_id=v.id,
                    rule_id=v.rule_id,
                    severity=v.severity,
                    original_description=v.description,
                    translated_description=trans_resp.translated_text or v.description,
                    citation=v.citation or "",
                )
            )

        # Compose spoken narration
        status_word = (
            STATUTORY_PHRASES["pass"].get(target_lang, "पास")
            if not translated_violations
            else STATUTORY_PHRASES["violation_detected"].get(target_lang, "उल्लंघन पाया गया")
        )

        total_violations = len(translated_violations)
        total_declarations = len(translated_fields)

        if target_lang == "hi":
            if total_violations == 0:
                summary_narration = (
                    f"निरीक्षण परिणाम: सभी {total_declarations} घोषणाएं विधिक मापविज्ञान नियमों के अनुरूप हैं। "
                    f"पैकेज पूरी तरह से पास है।"
                )
            else:
                top_v = translated_violations[0].translated_description
                summary_narration = (
                    f"निरीक्षण परिणाम: {total_violations} उल्लंघन पाए गए। प्रमुख समस्या: {top_v}। कृपया अधिकारी समीक्षा पूरी करें।"
                )
        elif target_lang == "mr":
            if total_violations == 0:
                summary_narration = (
                    f"तपासणी निकाल: सर्व {total_declarations} घोषणा नियमांनुसार वैध आहेत. उत्पादन पूर्णपणे पास झाले आहे."
                )
            else:
                top_v = translated_violations[0].translated_description
                summary_narration = f"तपासणी निकाल: {total_violations} उल्लंघन आढळले. मुख्य बाब: {top_v}."
        else:
            summary_narration = (
                f"Inspection results in {target_lang_obj.name}: {total_declarations} declarations checked, "
                f"{total_violations} violations found. Status: {status_word}."
            )

        is_offline = any(f.field_type in LEGAL_METROLOGY_DICTIONARY for f in inspection.fields) and (
            not self.is_live_configured
        )

        return InspectionTranslationResponse(
            inspection_id=inspection.id,
            target_language=target_lang,
            target_language_name=target_lang_obj.native_name,
            is_offline_fallback=is_offline,
            summary_narration=summary_narration,
            fields=translated_fields,
            violations=translated_violations,
        )

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------
    def _translate_offline(self, text: str, target_lang: str) -> str:
        """Local dictionary and heuristic mapping for Legal Metrology phrases."""
        clean = text.strip()
        lower = clean.lower()

        # Direct phrase mapping
        if "exceeds" in lower and "mrp" in lower:
            return STATUTORY_PHRASES["mrp_inflation"].get(target_lang, clean)
        if "quantity" in lower and ("mismatch" in lower or "conflict" in lower):
            return STATUTORY_PHRASES["net_quantity_mismatch"].get(target_lang, clean)

        for field_type, dict_map in LEGAL_METROLOGY_DICTIONARY.items():
            if field_type in lower or field_type.replace("_", " ") in lower:
                return dict_map.get(target_lang, clean)

        # Known country names
        if lower == "india":
            return "भारत" if target_lang in ("hi", "mr", "gu") else "இந்தியா" if target_lang == "ta" else clean
        if lower == "china":
            return "चीन" if target_lang in ("hi", "mr", "gu") else "சீனா" if target_lang == "ta" else clean

        return clean

    async def _call_bhashini_nmt(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str | None:
        """Performs live HTTP request to Bhashini ULCA NMT API."""
        headers = {
            "Content-Type": "application/json",
            "userID": self.user_id,
            "ulcaApiKey": self.api_key,
        }
        payload = {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": source_lang,
                            "targetLanguage": target_lang,
                        }
                    },
                }
            ],
            "inputData": {
                "input": [{"source": text}],
            },
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                tasks = data.get("pipelineResponse", [])
                for task in tasks:
                    if task.get("taskType") == "translation":
                        output = task.get("output", [])
                        if output and "target" in output[0]:
                            return output[0]["target"]
        return None

    async def _call_bhashini_tts(
        self,
        text: str,
        language: str,
        gender: str,
    ) -> str | None:
        """Performs live HTTP request to Bhashini ULCA TTS API."""
        headers = {
            "Content-Type": "application/json",
            "userID": self.user_id,
            "ulcaApiKey": self.api_key,
        }
        payload = {
            "pipelineTasks": [
                {
                    "taskType": "tts",
                    "config": {
                        "language": {"sourceLanguage": language},
                        "gender": gender,
                    },
                }
            ],
            "inputData": {
                "input": [{"source": text}],
            },
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                tasks = data.get("pipelineResponse", [])
                for task in tasks:
                    if task.get("taskType") == "tts":
                        audio = task.get("audio", [])
                        if audio and "audioContent" in audio[0]:
                            return audio[0]["audioContent"]
        return None
