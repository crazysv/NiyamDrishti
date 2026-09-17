import json
import re
from typing import Any

from app.services.extraction.base import BaseFieldExtractor
from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class ManufacturerAddressExtractor(BaseFieldExtractor):
    """
    Extracts Manufacturer, Packer, or Importer name and address per Rule 6(1)(a) of LM(PC) Rules.
    Identifies responsible entity role, company name, address lines, and 6-digit PIN code.
    """

    ROLE_PATTERN = re.compile(
        r"(?i)\b(MANUFACTURED\s*(?:&|AND)?\s*PACKED|MANUFACTURED|MFD\.?|MFG\.?|PACKED|PKD\.?|IMPORTED|IMP\.?|MARKETED|MKT\.?)\s*(?:BY\b|BY(?=[A-Z])|AT\b)?[:\s]*(.*)",
        re.IGNORECASE,
    )

    PINCODE_PATTERN = re.compile(r"(?<!\d)([1-9][0-9]{2}\s?[0-9]{3})(?!\d)")

    ROLE_MAP = {
        "mfd": "manufacturer",
        "mfg": "manufacturer",
        "manufactured": "manufacturer",
        "pkd": "packer",
        "packed": "packer",
        "manufactured & packed": "manufacturer_and_packer",
        "manufactured and packed": "manufacturer_and_packer",
        "imp": "importer",
        "imported": "importer",
        "mkt": "marketer",
        "marketed": "marketer",
    }

    MAJOR_FIELD_HEADERS = (
        "mrp",
        "net wt",
        "net qty",
        "batch",
        "mfg date",
        "use by",
        "exp date",
    )

    @property
    def field_type(self) -> str:
        return "manufacturer_address"

    @staticmethod
    def _union_box(lines: list[OCRLine]) -> dict[str, float]:
        left = min(line.bounding_box.x for line in lines)
        top = min(line.bounding_box.y for line in lines)
        right = max(line.bounding_box.x + line.bounding_box.w for line in lines)
        bottom = max(line.bounding_box.y + line.bounding_box.h for line in lines)
        return {"x": left, "y": top, "w": right - left, "h": bottom - top}

    @staticmethod
    def _is_near_address_line(anchor: OCRLine, candidate: OCRLine) -> bool:
        if anchor.source_image_id and candidate.source_image_id and anchor.source_image_id != candidate.source_image_id:
            return False
        first, second = anchor.bounding_box, candidate.bounding_box
        horizontal_gap = max(first.x - (second.x + second.w), second.x - (first.x + first.w), 0.0)
        vertical_gap = max(first.y - (second.y + second.h), second.y - (first.y + first.h), 0.0)
        return horizontal_gap <= 260 and vertical_gap <= 200

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        for idx, line in enumerate(lines):
            text = line.text
            match = self.ROLE_PATTERN.search(text)

            if match:
                raw_role = match.group(1).lower().strip()
                normalized_role = self.ROLE_MAP.get(raw_role, "manufacturer")

                # MFG/MFD/PKD are also common date headers. They identify a
                # business entity only when the text explicitly says "by" or
                # "at"; otherwise do not turn a manufacturing date into a
                # manufacturer-address declaration.
                if raw_role in {"mfd", "mfg", "pkd", "packed"} and not re.search(
                    r"(?i)\b(?:by|at)\b", text
                ):
                    continue

                address_parts = [text]
                address_lines = [line]
                # Look ahead up to 3 subsequent lines to collect complete multi-line address
                lookahead_idx = idx + 1
                found_pincode = None

                # Check if current line contains PIN code
                pin_match = self.PINCODE_PATTERN.search(text)
                if pin_match:
                    found_pincode = pin_match.group(1).replace(" ", "")

                while lookahead_idx < len(lines) and (lookahead_idx - idx) <= 3:
                    next_text = lines[lookahead_idx].text
                    # Stop lookahead if next line is another major field header (e.g. MRP, Net Qty)
                    if any(header in next_text.lower() for header in self.MAJOR_FIELD_HEADERS):
                        break

                    if not self._is_near_address_line(line, lines[lookahead_idx]):
                        lookahead_idx += 1
                        continue

                    address_parts.append(next_text)
                    address_lines.append(lines[lookahead_idx])
                    if not found_pincode:
                        next_pin_match = self.PINCODE_PATTERN.search(next_text)
                        if next_pin_match:
                            found_pincode = next_pin_match.group(1).replace(" ", "")
                    lookahead_idx += 1

                combined_address = ", ".join(address_parts)
                # Ignore isolated keyword matches (e.g. standalone "PKD." packing date header)
                if len(combined_address.strip()) <= 6 or not any(
                    c.isalpha() for c in combined_address[len(raw_role) :]
                ):
                    continue

                has_complete_pin = found_pincode is not None

                # Rule requires complete address with pincode
                confidence = line.confidence
                if has_complete_pin:
                    confidence = min(1.0, confidence + 0.05)

                parsed_payload: dict[str, Any] = {
                    "role": normalized_role,
                    "name_and_address": combined_address,
                    "pincode": found_pincode,
                    "has_valid_pincode": has_complete_pin,
                }

                declarations.append(
                    ExtractedDeclaration(
                        field_type=self.field_type,
                        raw_text=combined_address,
                        parsed_value=json.dumps(parsed_payload),
                        confidence=round(confidence, 4),
                        bounding_box=self._union_box(address_lines),
                        source_image_id=source_image_id,
                        verdict="pass" if has_complete_pin else "needs_review",
                        metadata=parsed_payload,
                    )
                )

        return declarations
