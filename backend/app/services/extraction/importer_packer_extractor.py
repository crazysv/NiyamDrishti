import re

from app.services.extraction.base import BaseFieldExtractor
from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class ImporterPackerExtractor(BaseFieldExtractor):
    """
    Extracts Packer, Importer, and Marketer details per Rule 6(1)(a) of LM(PC) Rules, 2011.
    Distinguishes separate packer/importer addresses from primary manufacturer.
    """

    field_type = "packer_importer"

    IMPORTER_PATTERN = re.compile(
        r"(?i)(?:IMPORTED\s*(?:BY|AND\s*MARKETED\s*BY|INTO\s*INDIA\s*BY)?|IMPORTER)[\s:.-]+([A-Z0-9\s,.-]+)",
        re.IGNORECASE,
    )

    PACKER_PATTERN = re.compile(
        r"(?i)(?:PACKED\s*(?:BY|AT)?|PACKAGING\s*BY)[\s:.-]+([A-Z0-9\s,.-]+)",
        re.IGNORECASE,
    )

    MARKETER_PATTERN = re.compile(
        r"(?i)(?:MARKETED\s*BY|DISTRIBUTED\s*BY)[\s:.-]+([A-Z0-9\s,.-]+)",
        re.IGNORECASE,
    )

    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        declarations: list[ExtractedDeclaration] = []

        for line in lines:
            text = line.text.strip()
            if len(text) < 6:
                continue

            # Check Importer
            imp_m = self.IMPORTER_PATTERN.search(text)
            if imp_m:
                val = imp_m.group(1).strip()
                if len(val) >= 3:
                    declarations.append(
                        ExtractedDeclaration(
                            field_type="importer_address",
                            raw_text=text,
                            parsed_value=val,
                            confidence=min(line.confidence, 0.93),
                            bounding_box=line.bounding_box.model_dump(),
                            source_image_id=source_image_id,
                            verdict="pass",
                            metadata={"role": "importer"},
                        )
                    )
                    continue

            # Check Packer
            pck_m = self.PACKER_PATTERN.search(text)
            if pck_m:
                val = pck_m.group(1).strip()
                if len(val) >= 3:
                    declarations.append(
                        ExtractedDeclaration(
                            field_type="packer_address",
                            raw_text=text,
                            parsed_value=val,
                            confidence=min(line.confidence, 0.92),
                            bounding_box=line.bounding_box.model_dump(),
                            source_image_id=source_image_id,
                            verdict="pass",
                            metadata={"role": "packer"},
                        )
                    )
                    continue

            # Check Marketer
            mkt_m = self.MARKETER_PATTERN.search(text)
            if mkt_m:
                val = mkt_m.group(1).strip()
                if len(val) >= 3:
                    declarations.append(
                        ExtractedDeclaration(
                            field_type="marketer_address",
                            raw_text=text,
                            parsed_value=val,
                            confidence=min(line.confidence, 0.90),
                            bounding_box=line.bounding_box.model_dump(),
                            source_image_id=source_image_id,
                            verdict="pass",
                            metadata={"role": "marketer"},
                        )
                    )

        return declarations
