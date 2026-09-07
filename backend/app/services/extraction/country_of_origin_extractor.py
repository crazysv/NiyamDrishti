import json
import re
from typing import Any

from app.services.extraction.base import BaseFieldExtractor
from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class CountryOfOriginExtractor(BaseFieldExtractor):
    """
    Extracts Country of Origin declaration per Rule 6(1)(j) of LM(PC) Rules.
    Identifies statements such as "Country of Origin: India" or "Made in India".
    """

    ORIGIN_PATTERN = re.compile(
        r"(?i)\b(?:COUNTRY\s+OF\s+ORIGIN|MADE\s+IN|PRODUCT\s+OF|ORIGIN)[\s:.-]*([A-Za-z\s]{3,30})\b",
        re.IGNORECASE,
    )

    STANDALONE_COUNTRY_PATTERN = re.compile(
        r"(?i)\b(INDIA|CHINA|THAILAND|VIETNAM|BANGLADESH|INDONESIA|MALAYSIA|GERMANY|JAPAN|USA|UNITED\s+STATES|UNITED\s+KINGDOM|FRANCE|ITALY)\b"
    )

    @property
    def field_type(self) -> str:
        return "country_of_origin"

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        for line in lines:
            text = line.text
            match = self.ORIGIN_PATTERN.search(text)
            country_name = ""

            if match:
                country_name = match.group(1).strip()
            elif any(k in text.lower() for k in ["origin", "made in", "product of"]):
                std_match = self.STANDALONE_COUNTRY_PATTERN.search(text)
                if std_match:
                    country_name = std_match.group(1).strip()

            if country_name:
                normalized_country = country_name.upper()
                parsed_payload: dict[str, Any] = {
                    "country": normalized_country,
                    "raw_country": country_name,
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
