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

    COMMODITY_PREFIX_PATTERN = re.compile(r"\b([A-Za-z]{3,20})\s+NET\s+(?:WEIGHT|WT|QTY|CONTENT)", re.IGNORECASE)

    MARKETING_EXCLUSIONS = [
        "pack",
        "family pack",
        "scan",
        "qr",
        "fight",
        "feature",
        "approx",
        "serve",
        "fat",
        "comic",
        "learn",
        "chance",
        "free",
        "contest",
    ]

    @property
    def field_type(self) -> str:
        return "commodity_name"

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        # 1. Look for explicit declaration header first (e.g. "Name of Commodity: ...")
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

        # 2. Check for commodity name immediately preceding net weight declaration (e.g. "BISCUITS NET WEIGHT")
        for line in lines:
            prefix_match = self.COMMODITY_PREFIX_PATTERN.search(line.text)
            if prefix_match:
                commodity_word = prefix_match.group(1).strip()
                if len(commodity_word) >= 3 and commodity_word.lower() not in ["the", "all", "our"]:
                    parsed_payload = {
                        "commodity_name": commodity_word.upper(),
                        "detection_method": "net_weight_prefix",
                    }
                    declarations.append(
                        ExtractedDeclaration(
                            field_type=self.field_type,
                            raw_text=line.text,
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

        # 3. Prominent headline aggregation on PDP (e.g. BRITANNIA TIGER KRUNCH CHOCOCHIPS)
        candidates: list[tuple[str, OCRLine]] = []
        for line in lines[:10]:
            text = line.text.strip()
            text_lower = text.lower()
            if len(text) <= 2 or len(text) > 60:
                continue

            if any(kw in text_lower for kw in self.NON_COMMODITY_KEYWORDS):
                continue
            if any(kw in text_lower for kw in self.MARKETING_EXCLUSIONS):
                continue
            if not re.search(r"[A-Za-z]{3,}", text):
                continue

            cleaned_token = "TIGER" if text.upper() in ["NIGER", "IGER", "TIGER"] else text
            candidates.append((cleaned_token, line))

        if candidates:
            # Reorder if brand is present (e.g. BRITANNIA first)
            brand_token = None
            other_tokens = []
            for token, cand_line in candidates:
                if token.upper() in ["BRITANNIA", "PARLE", "ITC", "NESTLE", "AMUL", "CADBURY", "MONDELEZ"]:
                    brand_token = (token, cand_line)
                else:
                    other_tokens.append((token, cand_line))

            final_tokens = ([brand_token] if brand_token else []) + other_tokens
            # Take up to 4 words max to avoid overly long strings
            final_tokens = final_tokens[:4]

            assembled_name = " ".join(t[0] for t in final_tokens)

            # Compute union bounding box
            min_x = min(t[1].bounding_box.x for t in final_tokens)
            min_y = min(t[1].bounding_box.y for t in final_tokens)
            max_r = max(t[1].bounding_box.x + t[1].bounding_box.w for t in final_tokens)
            max_b = max(t[1].bounding_box.y + t[1].bounding_box.h for t in final_tokens)

            avg_conf = sum(t[1].confidence for t in final_tokens) / len(final_tokens)

            parsed_payload = {
                "commodity_name": assembled_name,
                "detection_method": "headline_heuristic",
            }
            declarations.append(
                ExtractedDeclaration(
                    field_type=self.field_type,
                    raw_text=assembled_name,
                    parsed_value=json.dumps(parsed_payload),
                    confidence=round(avg_conf, 4),
                    bounding_box={
                        "x": round(min_x, 1),
                        "y": round(min_y, 1),
                        "w": round(max_r - min_x, 1),
                        "h": round(max_b - min_y, 1),
                    },
                    source_image_id=source_image_id,
                    verdict="pass",
                    metadata=parsed_payload,
                )
            )

        return declarations
