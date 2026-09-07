import json
import re
from typing import Any

from app.services.extraction.base import BaseFieldExtractor
from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class ConsumerCareExtractor(BaseFieldExtractor):
    """
    Extracts Consumer Care / Customer Helpline details per Rule 6(1)(n) of LM(PC) Rules.
    Identifies phone numbers, toll-free numbers, email addresses, and contact designations.
    """

    PHONE_PATTERN = re.compile(
        r"(?:1[-.]?800[-.\s]?\d{6,8}|1800[-.\s]?\d{6,8}|1800[-.\s]?\d{3,4}[-.\s]?\d{3,4}|(?:\+?91[-.\s]?)?[6-9]\d{9})"
    )

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")

    CARE_HEADER_PATTERN = re.compile(
        r"(?i)(?:CONSUMER|CUSTOMER|CONSMER)\s*(?:CARE|SERVICE|FEEDBACK|HELPLINE|CELL|SUPPORT|EXECUTIVE|EXECTIVE)|(?:FOR\s+FEEDBACK|FEEDBACK|QUERIES|COMPLAINTS|CONTACT\s+US|TOLL\s*FREE)",
        re.IGNORECASE,
    )

    @property
    def field_type(self) -> str:
        return "consumer_care"

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []
        skip_indices: set[int] = set()

        for idx, line in enumerate(lines):
            if idx in skip_indices:
                continue

            text = line.text
            text_lower = text.lower()
            # Avoid mistaking FSSAI license numbers for contact numbers
            if ("lic.no" in text_lower or "fssai" in text_lower) and not any(
                k in text_lower for k in ["care", "customer", "feedback", "helpline", "toll"]
            ):
                continue

            has_header = bool(self.CARE_HEADER_PATTERN.search(text))
            email_match = self.EMAIL_PATTERN.search(text)
            phone_matches = self.PHONE_PATTERN.findall(text)

            # Filter phone matches: if it's just a 10-digit number, require phone/contact indicator or +91
            valid_phones = []
            for p in phone_matches:
                p_clean = p.strip()
                if (
                    "1800" in p_clean
                    or "800-" in p_clean
                    or p_clean.startswith("+91")
                    or any(
                        indicator in text_lower
                        for indicator in ["ph", "tel", "call", "care", "helpline", "toll", "contact", "phone", "mob"]
                    )
                ):
                    valid_phones.append(p_clean)

            if has_header or email_match or valid_phones:
                collected_lines = [text]
                found_email = email_match.group(0) if email_match else None
                found_phones: list[str] = list(valid_phones)

                # If we matched a consumer care header or partial contact, look ahead up to 3 lines
                lookahead = idx + 1
                while lookahead < len(lines) and (lookahead - idx) <= 3:
                    next_line = lines[lookahead].text
                    next_lower = next_line.lower()
                    e_match = self.EMAIL_PATTERN.search(next_line)
                    p_matches = self.PHONE_PATTERN.findall(next_line)

                    if e_match and not found_email:
                        found_email = e_match.group(0)
                        collected_lines.append(next_line)
                        skip_indices.add(lookahead)
                    if p_matches:
                        for pm in p_matches:
                            pm_clean = pm.strip()
                            is_valid_indicator = (
                                "1800" in pm_clean
                                or "800-" in pm_clean
                                or pm_clean.startswith("+91")
                                or any(
                                    ind in next_lower or ind in text_lower
                                    for ind in [
                                        "ph",
                                        "tel",
                                        "call",
                                        "care",
                                        "helpline",
                                        "toll",
                                        "contact",
                                        "phone",
                                        "mob",
                                    ]
                                )
                            )
                            if is_valid_indicator and pm_clean not in found_phones:
                                found_phones.append(pm_clean)
                        if next_line not in collected_lines:
                            collected_lines.append(next_line)
                        skip_indices.add(lookahead)
                    lookahead += 1

                found_phone = found_phones[0] if found_phones else None

                if found_email or found_phone:
                    combined_text = " ".join(collected_lines)
                    confidence = line.confidence
                    if found_email and found_phone:
                        confidence = min(1.0, confidence + 0.05)

                    parsed_payload: dict[str, Any] = {
                        "email": found_email,
                        "phone": found_phone,
                        "has_email": found_email is not None,
                        "has_phone": found_phone is not None,
                    }

                    declarations.append(
                        ExtractedDeclaration(
                            field_type=self.field_type,
                            raw_text=combined_text,
                            parsed_value=json.dumps(parsed_payload),
                            confidence=round(confidence, 4),
                            bounding_box={
                                "x": line.bounding_box.x,
                                "y": line.bounding_box.y,
                                "w": line.bounding_box.w,
                                "h": line.bounding_box.h,
                            },
                            source_image_id=source_image_id,
                            verdict="pass" if (found_email or found_phone) else "needs_review",
                            metadata=parsed_payload,
                        )
                    )

        return declarations
