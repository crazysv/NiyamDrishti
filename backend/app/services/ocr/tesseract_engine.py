import logging
import shutil
from typing import Any

import numpy as np

from app.services.ocr.base import BaseOCREngine
from app.services.ocr.schemas import BoundingBox, OCRLine, OCRResult

logger = logging.getLogger(__name__)


class TesseractEngine(BaseOCREngine):
    """
    Tesseract OCR fallback engine integration (OCR-02).
    Extracts text tokens and aggregates them into lines with bounding boxes and confidences.
    """

    def __init__(self, tesseract_cmd: str | None = None) -> None:
        self.tesseract_cmd = tesseract_cmd

    @property
    def name(self) -> str:
        return "tesseract"

    def is_available(self) -> bool:
        """Checks if Tesseract binary is available on system PATH."""
        try:
            import pytesseract

            cmd = self.tesseract_cmd or pytesseract.pytesseract.tesseract_cmd
            return bool(shutil.which(cmd))
        except Exception:
            return False

    def extract(self, image: np.ndarray, source_image_id: str) -> OCRResult:
        """
        Executes Tesseract OCR on image array using image_to_data.
        Aggregates word-level tokens into lines.
        """
        try:
            import pytesseract
        except ImportError as e:
            raise RuntimeError("pytesseract is not installed") from e

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

        try:
            data: dict[str, list[Any]] = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        except Exception as e:
            logger.warning(f"Tesseract extraction failed: {e}")
            raise RuntimeError(f"Tesseract OCR failed: {e}") from e

        # Group words by (block_num, par_num, line_num)
        lines_dict: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
        n_boxes = len(data["text"])

        for i in range(n_boxes):
            word = str(data["text"][i]).strip()
            conf_str = str(data["conf"][i])
            try:
                conf_val = float(conf_str)
            except ValueError:
                conf_val = -1.0

            # Filter empty text or negative confidence tokens (separators)
            if not word or conf_val < 0:
                continue

            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            token_info = {
                "word": word,
                "conf": conf_val / 100.0,  # Normalize to 0.0-1.0
                "left": data["left"][i],
                "top": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i],
            }
            lines_dict.setdefault(key, []).append(token_info)

        lines: list[OCRLine] = []
        confidences: list[float] = []

        for line_idx, (_, words) in enumerate(lines_dict.items(), start=1):
            line_text = " ".join(w["word"] for w in words).strip()
            if not line_text:
                continue

            # Compute union bounding box for the line
            left = min(w["left"] for w in words)
            top = min(w["top"] for w in words)
            right = max(w["left"] + w["width"] for w in words)
            bottom = max(w["top"] + w["height"] for w in words)

            line_conf = float(sum(w["conf"] for w in words) / len(words))
            confidences.append(line_conf)

            bbox = BoundingBox(
                x=float(left),
                y=float(top),
                w=float(right - left),
                h=float(bottom - top),
                polygon=[
                    [float(left), float(top)],
                    [float(right), float(top)],
                    [float(right), float(bottom)],
                    [float(left), float(bottom)],
                ],
            )

            lines.append(
                OCRLine(
                    text=line_text,
                    confidence=round(line_conf, 4),
                    bounding_box=bbox,
                    source_image_id=source_image_id,
                    engine=self.name,
                    line_number=line_idx,
                )
            )

        avg_conf = round(float(sum(confidences) / len(confidences)), 4) if confidences else 0.0
        full_text = "\n".join([line.text for line in lines])

        return OCRResult(
            source_image_id=source_image_id,
            lines=lines,
            full_text=full_text,
            average_confidence=avg_conf,
            engine_used=self.name,
        )
