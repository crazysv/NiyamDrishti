import re

from app.services.extraction.base import BaseFieldExtractor
from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class DimensionsAndCountExtractor(BaseFieldExtractor):
    """
    Extracts package dimensions (e.g. 10 cm x 15 cm x 5 cm) and piece/unit counts
    (e.g. 10 N, 50 Pieces, Pack of 12) per Rule 6(1) and Rule 13 of LM(PC) Rules, 2011.
    """

    field_type = "dimension_count"

    # Pattern for 2D or 3D physical dimensions (e.g. 10 cm x 15 cm, 100 mm x 50 mm x 25 mm, 1.5 m x 2 m)
    DIMENSION_PATTERN = re.compile(
        r"(?i)(?:DIMENSIONS?|SIZE|MEASUREMENT)?[\s:.-]*([0-9]+(?:\.[0-9]+)?)\s*(MM|CM|M|INCH|INCHES|FT|FEET)?\s*[xX*×]\s*([0-9]+(?:\.[0-9]+)?)\s*(MM|CM|M|INCH|INCHES|FT|FEET)?(?:\s*[xX*×]\s*([0-9]+(?:\.[0-9]+)?)\s*(MM|CM|M|INCH|INCHES|FT|FEET)?)?",
        re.IGNORECASE,
    )

    # Pattern for piece/unit count (e.g. "Pack of 10", "10 N", "50 Pieces", "12 Units", "Count: 20 pcs")
    COUNT_PATTERN = re.compile(
        r"(?i)(?:PACK\s*OF|COUNT|QUANTITY|QTY|NUMBER|NO\.?\s*OF\s*PIECES|CONTENTS)?[\s:.-]*\b([0-9]+)\s*(?:N|UNITS?|PIECES?|PCS|ITEMS?|TABLETS?|CAPSULES?|PACKS?|SHEETS?|PAIRS?)\b",
        re.IGNORECASE,
    )

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        for line in lines:
            text = line.text.strip()
            if not text:
                continue

            # Check dimensions first
            dim_match = self.DIMENSION_PATTERN.search(text)
            if dim_match:
                d1, u1, d2, u2, d3, u3 = dim_match.groups()
                # Ensure it has multiplication operator and valid numbers
                if d1 and d2:
                    unit = u3 or u2 or u1 or "cm"
                    unit = unit.lower()
                    dim_str = f"{d1} x {d2}" + (f" x {d3}" if d3 else "") + f" {unit}"
                    declarations.append(
                        ExtractedDeclaration(
                            field_type="dimensions",
                            raw_text=text,
                            parsed_value=dim_str,
                            confidence=min(line.confidence, 0.95),
                            bounding_box=line.bounding_box.model_dump(),
                            source_image_id=source_image_id,
                            verdict="pass",
                            metadata={
                                "type": "dimension",
                                "dimensions": [float(d1), float(d2)] + ([float(d3)] if d3 else []),
                                "unit": unit,
                            },
                        )
                    )
                    continue

            # Check piece count
            cnt_match = self.COUNT_PATTERN.search(text)
            if cnt_match:
                count_val = cnt_match.group(1)
                declarations.append(
                    ExtractedDeclaration(
                        field_type="item_count",
                        raw_text=text,
                        parsed_value=f"{count_val} N",
                        confidence=min(line.confidence, 0.94),
                        bounding_box=line.bounding_box.model_dump(),
                        source_image_id=source_image_id,
                        verdict="pass",
                        metadata={
                            "type": "count",
                            "count": int(count_val),
                            "standard_notation": f"{count_val} N",
                        },
                    )
                )

        return declarations
