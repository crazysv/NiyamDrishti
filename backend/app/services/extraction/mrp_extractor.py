import json
import re
from typing import Any

from app.services.extraction.base import BaseFieldExtractor
from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class MRPExtractor(BaseFieldExtractor):
    """
    Extracts Maximum Retail Price (MRP) declaration per Rule 6(1)(e) of LM(PC) Rules.
    Verifies price magnitude, currency code, and tax-inclusivity statement.
    """

    MRP_PATTERN = re.compile(
        r"(?i)(?:M\.?R\.?P\.?|MAX(?:IMUM)?\s+RETAIL\s+PRICE|RETAIL\s+PRICE|PRICE)[\s:.-]*(?:RS\.?|₹|INR)?\s*([0-9]+(?:[.,][0-9]{1,2})?)",
        re.IGNORECASE,
    )

    TAX_INCLUSIVE_PATTERN = re.compile(
        r"(?i)(?:INCL\.?(?:USIVE)?(?:\s+OF)?\s+ALL\s+TAXES|INCL\.?\s+ALL\s+TAXES|ALL\s+TAXES\s+INCL)",
        re.IGNORECASE,
    )

    @property
    def field_type(self) -> str:
        return "mrp"

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        for idx, line in enumerate(lines):
            text = line.text
            match = self.MRP_PATTERN.search(text)

            if match:
                raw_price_str = match.group(1).replace(",", ".")
                try:
                    price_val = float(raw_price_str)
                except ValueError:
                    continue

                if price_val <= 0:
                    continue

                # Check current line or next line for "incl. of all taxes"
                has_taxes = bool(self.TAX_INCLUSIVE_PATTERN.search(text))
                combined_text = text

                if not has_taxes and idx + 1 < len(lines):
                    next_line_text = lines[idx + 1].text
                    if self.TAX_INCLUSIVE_PATTERN.search(next_line_text):
                        has_taxes = True
                        combined_text = f"{text} {next_line_text}"

                confidence = line.confidence
                # Boost confidence if official "inclusive of all taxes" qualifier is explicitly present
                if has_taxes:
                    confidence = min(1.0, confidence + 0.05)

                parsed_payload: dict[str, Any] = {
                    "amount": round(price_val, 2),
                    "currency": "INR",
                    "inclusive_of_all_taxes": has_taxes,
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
                        verdict="pass" if has_taxes else "needs_review",
                        metadata=parsed_payload,
                    )
                )

        return declarations
