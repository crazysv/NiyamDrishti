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

    PHONE_PATTERN = re.compile(r"(?:1800[\s-]?\d{3}[\s-]?\d{3,4}|\+?91[\s-]?\d{10}|\b\d{10,11}\b)")

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")

    CARE_HEADER_PATTERN = re.compile(
        r"(?i)(?:CONSUMER|CUSTOMER)\s*(?:CARE|SERVICE|FEEDBACK|HELPLINE|CELL|SUPPORT)|(?:FOR\s+COMPLAINTS|FEEDBACK|QUERIES|CONTACT\s+US)",
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
            has_header = bool(self.CARE_HEADER_PATTERN.search(text))
            email_match = self.EMAIL_PATTERN.search(text)
            phone_match = self.PHONE_PATTERN.search(text)

            if has_header or email_match or phone_match:
                collected_lines = [text]
                found_email = email_match.group(0) if email_match else None
                found_phone = phone_match.group(0) if phone_match else None

                # If we matched a consumer care header, check next 2 lines for contact channels
                if has_header and not (found_email and found_phone):
                    lookahead = idx + 1
                    while lookahead < len(lines) and (lookahead - idx) <= 2:
                        next_line = lines[lookahead].text
                        e_match = self.EMAIL_PATTERN.search(next_line)
                        p_match = self.PHONE_PATTERN.search(next_line)

                        if e_match and not found_email:
                            found_email = e_match.group(0)
                        if p_match and not found_phone:
                            found_phone = p_match.group(0)

                        if e_match or p_match:
                            collected_lines.append(next_line)
                            skip_indices.add(lookahead)
                        lookahead += 1

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
