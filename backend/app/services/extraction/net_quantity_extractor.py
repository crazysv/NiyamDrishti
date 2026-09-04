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

    # Multi-pack quantity formula e.g. "4Nx100g=400g" or "4 N x 100 g = 400 g"
    MULTIPACK_PATTERN = re.compile(
        r"(?i)\b([0-9]+)\s*(?:N|U|PCS|PIECES|UNITS)?\s*[xX*]\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)\b"
    )

    NUTRITION_EXCLUSION = [
        "nutrition",
        "per 100",
        "per100",
        "per serve",
        "approx",
        "energy",
        "protein",
        "carbohydrate",
        "fat",
        "sodium",
        "sugar",
        "cholesterol",
        "trans fat",
        "saturated",
        "dietary",
        "kcal",
    ]

    @property
    def field_type(self) -> str:
        return "net_quantity"

    def normalize_unit(self, raw_unit: str) -> str:
        clean = raw_unit.lower().strip()
        return self.UNIT_NORMALIZATION.get(clean, clean)

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        # 1. First check for multi-pack formula (highest specificity, e.g. 4Nx100g=400g)
        for idx, line in enumerate(lines):
            text = line.text
            multi_match = self.MULTIPACK_PATTERN.search(text)
            if multi_match:
                count_val = int(multi_match.group(1))
                unit_qty = float(multi_match.group(2))
                total_qty = float(multi_match.group(4))
                final_unit_raw = multi_match.group(5)

                std_unit = self.normalize_unit(final_unit_raw)
                combined_raw = text
                # Check previous line for "NET WEIGHT"
                if idx > 0 and any(k in lines[idx - 1].text.lower() for k in ["net", "wt", "weight"]):
                    combined_raw = f"{lines[idx - 1].text} {text}"

                parsed_payload: dict[str, Any] = {
                    "value": total_qty,
                    "unit": std_unit,
                    "raw_unit": final_unit_raw,
                    "is_multipack": True,
                    "units_count": count_val,
                    "unit_quantity": unit_qty,
                }

                declarations.append(
                    ExtractedDeclaration(
                        field_type=self.field_type,
                        raw_text=combined_raw,
                        parsed_value=json.dumps(parsed_payload),
                        confidence=round(min(1.0, line.confidence + 0.05), 4),
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

        # 2. Standard net quantity search with strict exclusion of nutrition lines
        for idx, line in enumerate(lines):
            text = line.text
            text_lower = text.lower()

            # Disqualify nutritional facts table lines from net weight declaration
            if any(k in text_lower for k in self.NUTRITION_EXCLUSION):
                continue

            match = self.NET_QTY_PATTERN.search(text)
            has_prefix = True

            if not match and any(
                k in text_lower
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
                # Check current line or nearby lines (above and below)
                match = self.STANDALONE_QTY_PATTERN.search(text)
                target_line = line
                if not match:
                    for offset in [-1, 1, -2, 2, -3, 3]:
                        target_idx = idx + offset
                        if 0 <= target_idx < len(lines):
                            cand_text = lines[target_idx].text
                            if not any(k in cand_text.lower() for k in self.NUTRITION_EXCLUSION):
                                match = self.STANDALONE_QTY_PATTERN.search(cand_text)
                                if match:
                                    text = f"{line.text} : {cand_text}"
                                    target_line = lines[target_idx]
                                    has_prefix = True
                                    break
                else:
                    has_prefix = True

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

                parsed_payload = {
                    "value": qty_val,
                    "unit": std_unit,
                    "raw_unit": unit_str,
                }

                bbox_src = target_line if "target_line" in locals() else line
                declarations.append(
                    ExtractedDeclaration(
                        field_type=self.field_type,
                        raw_text=text,
                        parsed_value=json.dumps(parsed_payload),
                        confidence=round(confidence, 4),
                        bounding_box={
                            "x": bbox_src.bounding_box.x,
                            "y": bbox_src.bounding_box.y,
                            "w": bbox_src.bounding_box.w,
                            "h": bbox_src.bounding_box.h,
                        },
                        source_image_id=source_image_id,
                        verdict="pass",
                        metadata=parsed_payload,
                    )
                )

        return declarations
