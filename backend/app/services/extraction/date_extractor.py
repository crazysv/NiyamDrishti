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
        r"(?i)(?:MFD\.?|MFG\.?|DATE\s+OF\s+MFG|DATE\s+OF\s+PACKING|PKD\.?|PACKED\s+ON|DOM|DOP|MFG\s+DATE)[\s:.-]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{1,2}[/-][0-9]{2,4}|(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[a-z]*[\s,.-]+[0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{2,4})",
        re.IGNORECASE,
    )

    STANDALONE_DATE_PATTERN = re.compile(
        r"\b(?:(0[1-9]|[12][0-9]|3[01])[/-](0[1-9]|1[0-2])[/-](20[2-3][0-9]|[2-3][0-9])|(0[1-9]|1[0-2])[/-](20[2-3][0-9]|[2-3][0-9]))\b"
    )

    EXPIRY_HEADER_PATTERN = re.compile(
        r"(?i)(?:USE\s+BY|EXP(?:IRY)?\.?|BEST\s+BEFORE|EXP\s+DATE|BB)[\s:.-]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{1,2}[/-][0-9]{2,4}|(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[a-z]*[\s,.-]+[0-9]{2,4})?",
        re.IGNORECASE,
    )

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

    def normalize_date_string(self, raw_date: str) -> tuple[str, str, str]:
        """Returns (month_str, year_str, day_str) e.g. ('07', '2026', '01')."""
        clean = raw_date.strip().replace("-", "/").replace(".", "/")
        parts = clean.split("/")

        if len(parts) == 2:
            m, y = parts[0].strip(), parts[1].strip()
            if len(y) == 2:
                y = f"20{y}"
            if len(m) == 1:
                m = f"0{m}"
            return m, y, ""
        elif len(parts) == 3:
            # DD/MM/YYYY format
            d, m, y = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if len(y) == 2:
                y = f"20{y}"
            if len(m) == 1:
                m = f"0{m}"
            if len(d) == 1:
                d = f"0{d}"
            return m, y, d

        # Check named month (e.g. "AUG 2026")
        for name, num in self.MONTH_MAP.items():
            if name in raw_date.lower():
                year_match = re.search(r"\b(20[2-3][0-9]|[2-3][0-9])\b", raw_date)
                if year_match:
                    y = year_match.group(1)
                    if len(y) == 2:
                        y = f"20{y}"
                    return num, y, ""

        return "", "", ""

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        # Collect all standalone date tokens and their line indices
        date_candidates: list[tuple[int, str, OCRLine]] = []
        for idx, line in enumerate(lines):
            # Check for standalone date tokens
            for match in self.STANDALONE_DATE_PATTERN.finditer(line.text):
                date_candidates.append((idx, match.group(0), line))

        # Check for explicit date headers
        for idx, line in enumerate(lines):
            text = line.text
            match = self.DATE_HEADER_PATTERN.search(text)
            raw_match_str = ""
            matched_line = line
            exp_payload = None

            if match and match.group(1):
                raw_match_str = match.group(1)
            elif any(k in text.lower() for k in ["mfd", "mfg", "pkd", "packed"]):
                std_match = self.STANDALONE_DATE_PATTERN.search(text)
                if std_match:
                    raw_match_str = std_match.group(0)
                elif date_candidates:
                    # Look in nearby lines (prefer closest index, within ±8 lines or spatial proximity)
                    # If multiple dates are found (e.g. PKD date and USE BY date), sort chronologically
                    # Manufacturing/packing date is always the earlier date.
                    valid_dates = []
                    for c_idx, c_date, c_line in date_candidates:
                        m, y, d = self.normalize_date_string(c_date)
                        if m and y:
                            valid_dates.append((y, m, d if d else "01", c_date, c_line))

                    if valid_dates:
                        valid_dates.sort(key=lambda t: (t[0], t[1], t[2]))
                        # The earliest date is the manufacturing/packing date
                        earliest = valid_dates[0]
                        raw_match_str = earliest[3]
                        matched_line = earliest[4]
                        # If there is a second (later) date, it is the expiry/use-by date
                        if len(valid_dates) > 1:
                            exp_date = valid_dates[-1]
                            exp_payload = f"{exp_date[2]}/{exp_date[1]}/{exp_date[0]}"

            if raw_match_str:
                month, year, day = self.normalize_date_string(raw_match_str)
                if month and year:
                    formatted_val = f"{month}/{year}" if not day else f"{day}/{month}/{year}"
                    parsed_payload: dict[str, Any] = {
                        "month": month,
                        "year": year,
                        "day": day if day else None,
                        "formatted": formatted_val,
                    }
                    if exp_payload:
                        parsed_payload["expiry_date"] = exp_payload

                    combined_raw = f"{text} -> {raw_match_str}" if matched_line != line else text
                    confidence = max(line.confidence, matched_line.confidence)

                    declarations.append(
                        ExtractedDeclaration(
                            field_type=self.field_type,
                            raw_text=combined_raw,
                            parsed_value=json.dumps(parsed_payload),
                            confidence=round(confidence, 4),
                            bounding_box={
                                "x": matched_line.bounding_box.x,
                                "y": matched_line.bounding_box.y,
                                "w": matched_line.bounding_box.w,
                                "h": matched_line.bounding_box.h,
                            },
                            source_image_id=source_image_id,
                            verdict="pass",
                            metadata=parsed_payload,
                        )
                    )
                    # Don't duplicate if multiple references to same header
                    break

        return declarations
