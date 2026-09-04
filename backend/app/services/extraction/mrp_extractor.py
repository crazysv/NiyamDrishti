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

    PRICE_NUMBER_PATTERN = re.compile(r"(?:RS\.?|₹|INR)?\s*([0-9]+(?:[.,][0-9]{1,2})?)(?:\s*\/-\s*)?", re.IGNORECASE)

    USP_PATTERN = re.compile(
        r"(?:(?:UNIT\s+SALE\s+PRICE|USP)[\s:.-]*)?(?:RS\.?|₹|INR)?\s*([0-9]+(?:\.[0-9]+)?)\s*[\/]\s*([a-zA-Z]+)",
        re.IGNORECASE,
    )

    @property
    def field_type(self) -> str:
        return "mrp"

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        # 1. Direct single-line regex search
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

                # Check current line, next line, or previous line for "incl. of all taxes"
                has_taxes = bool(self.TAX_INCLUSIVE_PATTERN.search(text))
                combined_text = text

                for offset in [1, -1, 2]:
                    target_idx = idx + offset
                    if 0 <= target_idx < len(lines):
                        cand_text = lines[target_idx].text
                        if self.TAX_INCLUSIVE_PATTERN.search(cand_text):
                            has_taxes = True
                            combined_text = f"{text} {cand_text}"
                            break

                confidence = line.confidence
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

        if declarations:
            return declarations

        # 2. Multi-line / tabular search for standalone "MRP" header
        for idx, line in enumerate(lines):
            text_clean = line.text.strip().lower().replace(" ", "").replace(".", "")
            if "mrp" in text_clean or "retailprice" in text_clean:
                # Find nearby lines (index distance <= 8 or spatial x/y proximity <= 60px)
                nearby_candidates = []
                for other_idx, other_line in enumerate(lines):
                    if other_idx == idx:
                        continue
                    idx_dist = abs(other_idx - idx)
                    dx = abs(other_line.bounding_box.x - line.bounding_box.x)
                    dy = abs(other_line.bounding_box.y - line.bounding_box.y)
                    if idx_dist <= 8 or dx <= 60 or dy <= 60:
                        nearby_candidates.append((other_idx, other_line))

                # Check for unit sale price first
                usp_info = None
                for _, cand_line in nearby_candidates:
                    usp_m = self.USP_PATTERN.search(cand_line.text)
                    if usp_m:
                        try:
                            usp_val = float(usp_m.group(1))
                            usp_unit = usp_m.group(2).lower()
                            usp_info = {"unit_sale_price": usp_val, "unit_sale_unit": usp_unit}
                        except ValueError:
                            pass

                # Check for price number
                price_val = None
                price_line = None
                combined_raw = line.text

                # Look for decimal numbers (e.g. 30.00, 130.00)
                for _, cand_line in nearby_candidates:
                    c_text = cand_line.text.strip()
                    # Skip date-like lines, codes, and USP lines
                    if "/" in c_text or ":" in c_text or "g" in c_text.lower():
                        continue
                    num_m = re.search(r"\b([0-9]{1,4}(?:\.[0-9]{2})?)\b", c_text)
                    if num_m:
                        raw_num = num_m.group(1)
                        try:
                            val = float(raw_num)
                            if 5 <= val <= 50000:
                                price_val = val
                                price_line = cand_line
                                combined_raw = f"{line.text} {c_text}"
                                break
                        except ValueError:
                            pass

                # Check if there was an adjacent single digit on the same vertical column
                # (e.g. OCR split "130.00" into "1" and "30.00")
                if price_val is not None and price_val < 100 and price_line is not None:
                    for _, digit_line in nearby_candidates:
                        d_text = digit_line.text.strip()
                        if d_text.isdigit() and len(d_text) == 1:
                            dx = abs(digit_line.bounding_box.x - price_line.bounding_box.x)
                            if dx <= 25:
                                # Prepend the digit
                                stitched = float(f"{d_text}{price_val:.2f}")
                                price_val = stitched
                                combined_raw = f"{line.text} {d_text} {price_line.text}"
                                break

                if price_val is not None:
                    # Check tax-inclusivity across all nearby lines
                    has_taxes = any(
                        self.TAX_INCLUSIVE_PATTERN.search(cand.text) or "tax" in cand.text.lower()
                        for _, cand in nearby_candidates
                    )

                    parsed_payload = {
                        "amount": round(price_val, 2),
                        "currency": "INR",
                        "inclusive_of_all_taxes": has_taxes,
                    }
                    if usp_info:
                        parsed_payload.update(usp_info)

                    declarations.append(
                        ExtractedDeclaration(
                            field_type=self.field_type,
                            raw_text=combined_raw,
                            parsed_value=json.dumps(parsed_payload),
                            confidence=round(line.confidence, 4),
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
                    break

        return declarations
