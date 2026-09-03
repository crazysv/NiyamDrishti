import json
import re
from typing import Any

from app.services.extraction.base import BaseFieldExtractor
from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class CommodityNameExtractor(BaseFieldExtractor):
    """
    Extracts Generic or Common Commodity Name per Rule 6(1)(b) of LM(PC) Rules.
    Identifies explicit headers like "Name of Commodity: ..." or top product naming text.
    """

    EXPLICIT_NAME_PATTERN = re.compile(
        r"(?i)\b(?:NAME\s+OF\s+(?:THE\s+)?COMMODITY|COMMODITY\s+NAME|PRODUCT\s+NAME|COMMODITY|PRODUCT)[\s:.-]+([A-Za-z0-9\s,&.-]{3,60})\b",
        re.IGNORECASE,
    )

    NON_COMMODITY_KEYWORDS = {
        "mrp",
        "net wt",
        "net qty",
        "batch",
        "mfg",
        "exp",
        "pkd",
        "consumer",
        "customer",
        "country",
        "ingredients",
        "nutrition",
    }

    @property
    def field_type(self) -> str:
        return "commodity_name"

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        # 1. Look for explicit declaration header first
        for line in lines:
            text = line.text
            match = self.EXPLICIT_NAME_PATTERN.search(text)
            if match:
                commodity_name = match.group(1).strip()
                if commodity_name:
                    parsed_payload: dict[str, Any] = {
                        "commodity_name": commodity_name,
                        "detection_method": "explicit_header",
                    }
                    declarations.append(
                        ExtractedDeclaration(
                            field_type=self.field_type,
                            raw_text=text,
                            parsed_value=json.dumps(parsed_payload),
                            confidence=round(line.confidence, 4),
                            bounding_box={
                                "x": line.bounding_box.x,
                                "y": line.bounding_box.y,
                                "w": line.bounding_box.w,
                                "h": line.bounding_box.h,
                            },
                            source_image_id=source_image_id,
                            verdict="pass",
                            metadata=parsed_payload,
                        )
                    )
                    return declarations

        # 2. Heuristic fallback: Top prominent line that is not a metadata/regulatory line
        for line in lines[:5]:
            text = line.text.strip()
            text_lower = text.lower()
            if len(text) < 4 or len(text) > 60:
                continue

            # Skip lines matching known keywords
            if any(keyword in text_lower for keyword in self.NON_COMMODITY_KEYWORDS):
                continue

            # Must contain letters
            if not re.search(r"[A-Za-z]{3,}", text):
                continue

            parsed_payload = {
                "commodity_name": text,
                "detection_method": "headline_heuristic",
            }
            declarations.append(
                ExtractedDeclaration(
                    field_type=self.field_type,
                    raw_text=text,
                    parsed_value=json.dumps(parsed_payload),
                    confidence=round(max(0.5, line.confidence - 0.1), 4),
                    bounding_box={
                        "x": line.bounding_box.x,
                        "y": line.bounding_box.y,
                        "w": line.bounding_box.w,
                        "h": line.bounding_box.h,
                    },
                    source_image_id=source_image_id,
                    verdict="needs_review",
                    metadata=parsed_payload,
                )
            )
            break

        return declarations
