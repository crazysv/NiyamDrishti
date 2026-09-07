import re

from app.services.extraction.base import BaseFieldExtractor
from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class RSPExtractor(BaseFieldExtractor):
    """
    Extracts Retail Sale Price (RSP) mandatory declaration under the Legal Metrology
    (Packaged Commodities) Second Amendment Rules, 2025 (effective 1 Feb 2026, G.S.R. 881(E)),
    specifically required on pan masala and tobacco packages.
    """

    field_type = "rsp"

    RSP_PATTERN = re.compile(
        r"(?i)(?:R\.?S\.?P\.?|RETAIL\s*SALE\s*PRICE)[\s:.-]*(?:RS\.?|INR|₹)?\s*([0-9]+(?:\.[0-9]{1,2})?)",
        re.IGNORECASE,
    )

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        for line in lines:
            text = line.text.strip()
            match = self.RSP_PATTERN.search(text)
            if match:
                price_val = float(match.group(1))
                has_inclusive = "INCL" in text.upper() or "TAX" in text.upper()
                declarations.append(
                    ExtractedDeclaration(
                        field_type="rsp",
                        raw_text=text,
                        parsed_value=f"Rs. {price_val:.2f}",
                        confidence=min(line.confidence, 0.95),
                        bounding_box=line.bounding_box.model_dump(),
                        source_image_id=source_image_id,
                        verdict="pass",
                        metadata={
                            "price": price_val,
                            "inclusive_of_taxes": has_inclusive,
                            "amendment": "LM(PC) Second Amendment 2025/2026",
                        },
                    )
                )

        return declarations
