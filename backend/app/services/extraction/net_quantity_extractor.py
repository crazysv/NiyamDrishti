import json
import re
from typing import Any

from app.services.extraction.base import BaseFieldExtractor
from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class NetQuantityExtractor(BaseFieldExtractor):
    """
    Extracts Net Quantity declaration per Rule 6(1)(c), Rule 12, and Rule 13 of LM(PC) Rules.
    Standardizes units to metric SI or item count (g, kg, ml, l, m, pieces/N/U).
    """

    NET_QTY_PATTERN = re.compile(
        r"(?i)(?:NET\s*(?:WT\.?|WEIGHT|QTY\.?|QUANTITY|VOL(?:UME)?|CONTENT)?|WEIGHT|QUANTITY|QTY)[\s:.-]*([0-9]+(?:\.[0-9]+)?)\s*(KG|KILOGRAMS?|GMS?|GM|GRAMS?|G|LTR?|LITRES?|LITERS?|L|MILLILITRES?|MILLILITERS?|ML|METERS?|METRES?|M|CENTIMETERS?|CENTIMETRES?|CM|PIECES?|PCS|UNITS?|U|N)\b",
        re.IGNORECASE,
    )

    # Standalone quantity without prefix (e.g. "500 g", "1 kg", "750 ml")
    STANDALONE_QTY_PATTERN = re.compile(
        r"\b([0-9]+(?:\.[0-9]+)?)\s*(KG|KILOGRAMS?|GMS?|GM|GRAMS?|G|LTR?|LITRES?|LITERS?|L|MILLILITRES?|MILLILITERS?|ML|METERS?|METRES?|M|CENTIMETERS?|CENTIMETRES?|CM|PIECES?|PCS|UNITS?|U|N)\b",
        re.IGNORECASE,
    )

    UNIT_NORMALIZATION = {
        "kg": "kg",
        "kilogram": "kg",
        "kilograms": "kg",
        "g": "g",
        "gm": "g",
        "gms": "g",
        "gram": "g",
        "grams": "g",
        "l": "l",
        "lt": "l",
        "ltr": "l",
        "litre": "l",
        "litres": "l",
        "liter": "l",
        "liters": "l",
        "ml": "ml",
        "millilitre": "ml",
        "millilitres": "ml",
        "milliliter": "ml",
        "milliliters": "ml",
        "m": "m",
        "meter": "m",
        "meters": "m",
        "metre": "m",
        "metres": "m",
        "cm": "cm",
        "centimeter": "cm",
        "centimeters": "cm",
        "centimetre": "cm",
        "centimetres": "cm",
        "pcs": "pieces",
        "piece": "pieces",
        "pieces": "pieces",
        "u": "pieces",
        "unit": "pieces",
        "units": "pieces",
        "n": "pieces",
    }

    @property
    def field_type(self) -> str:
        return "net_quantity"

    def normalize_unit(self, raw_unit: str) -> str:
        clean = raw_unit.lower().strip()
        return self.UNIT_NORMALIZATION.get(clean, clean)

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        for line in lines:
            text = line.text
            match = self.NET_QTY_PATTERN.search(text)
            has_prefix = True

            if not match and any(
                k in text.lower()
                for k in [
                    "net",
                    "wt",
                    "weight",
                    "qty",
                    "quantity",
                    "content",
                    "vol",
                ]
            ):
                match = self.STANDALONE_QTY_PATTERN.search(text)
                has_prefix = False

            if match:
                qty_str = match.group(1)
                unit_str = match.group(2)

                try:
                    qty_val = float(qty_str)
                except ValueError:
                    continue

                if qty_val <= 0:
                    continue

                std_unit = self.normalize_unit(unit_str)
                confidence = line.confidence
                if has_prefix:
                    confidence = min(1.0, confidence + 0.05)

                parsed_payload: dict[str, Any] = {
                    "value": qty_val,
                    "unit": std_unit,
                    "raw_unit": unit_str,
                }

                declarations.append(
                    ExtractedDeclaration(
                        field_type=self.field_type,
                        raw_text=text,
                        parsed_value=json.dumps(parsed_payload),
                        confidence=round(confidence, 4),
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
