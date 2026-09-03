import json
import re
from typing import Any

from app.services.extraction.base import BaseFieldExtractor
from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class MfgDateExtractor(BaseFieldExtractor):
    """
    Extracts Month and Year of Manufacture / Packing per Rule 6(1)(d) of LM(PC) Rules.
    Normalizes dates into standard MM/YYYY representation.
    """

    DATE_HEADER_PATTERN = re.compile(
        r"(?i)(?:MFD\.?|MFG\.?|DATE\s+OF\s+MFG|DATE\s+OF\s+PACKING|PKD\.?|PACKED\s+ON|DOM|DOP|MFG\s+DATE)[\s:.-]*([0-9]{1,2}[/-][0-9]{2,4}|(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[a-z]*[\s,.-]+[0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{2,4})",
        re.IGNORECASE,
    )

    STANDALONE_DATE_PATTERN = re.compile(r"\b(0[1-9]|1[0-2])[/-](20[2-3][0-9]|[2-3][0-9])\b")

    MONTH_MAP = {
        "jan": "01",
        "feb": "02",
        "mar": "03",
        "apr": "04",
        "may": "05",
        "jun": "06",
        "jul": "07",
        "aug": "08",
        "sep": "09",
        "oct": "10",
        "nov": "11",
        "dec": "12",
    }

    @property
    def field_type(self) -> str:
        return "mfg_date"

    def normalize_date_string(self, raw_date: str) -> tuple[str, str]:
        """Returns (month_str, year_str) e.g. ('08', '2026')."""
        clean = raw_date.strip().replace("-", "/").replace(".", "/")
        parts = clean.split("/")

        if len(parts) == 2:
            m, y = parts[0].strip(), parts[1].strip()
            if len(y) == 2:
                y = f"20{y}"
            if len(m) == 1:
                m = f"0{m}"
            return m, y
        elif len(parts) == 3:
            # DD/MM/YYYY format
            _, m, y = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if len(y) == 2:
                y = f"20{y}"
            if len(m) == 1:
                m = f"0{m}"
            return m, y

        # Check named month (e.g. "AUG 2026")
        for name, num in self.MONTH_MAP.items():
            if name in raw_date.lower():
                year_match = re.search(r"\b(20[2-3][0-9]|[2-3][0-9])\b", raw_date)
                if year_match:
                    y = year_match.group(1)
                    if len(y) == 2:
                        y = f"20{y}"
                    return num, y

        return "", ""

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        for line in lines:
            text = line.text
            match = self.DATE_HEADER_PATTERN.search(text)
            raw_match_str = ""

            if match:
                raw_match_str = match.group(1)
            elif any(k in text.lower() for k in ["mfd", "mfg", "pkd", "packed"]):
                std_match = self.STANDALONE_DATE_PATTERN.search(text)
                if std_match:
                    raw_match_str = std_match.group(0)

            if raw_match_str:
                month, year = self.normalize_date_string(raw_match_str)
                if month and year:
                    parsed_payload: dict[str, Any] = {
                        "month": month,
                        "year": year,
                        "formatted": f"{month}/{year}",
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
