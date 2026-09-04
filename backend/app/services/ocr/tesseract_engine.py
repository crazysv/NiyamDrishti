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
        Executes Tesseract OCR on image array.
        Uses --psm 11 (sparse text — finds text anywhere regardless of layout) and
        --oem 1 (LSTM only) for best accuracy on consumer packaging with stylised fonts.
        Applies lightweight grayscale+adaptive-threshold preprocessing (~5MB, not the
        200MB full OpenCV pipeline) to improve read rate on coloured/patterned backgrounds.
        """
        try:
            import pytesseract
        except ImportError as e:
            raise RuntimeError("pytesseract is not installed") from e

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

        # Preprocessing: grayscale only — let Tesseract do its own Otsu binarization.
        # DO NOT apply adaptive threshold here. On dark-background packaging (e.g. the
        # purple Britannia packet), THRESH_BINARY outputs white-text-on-black (inverted),
        # causing Tesseract to read texture noise as text instead of the actual words.
        # Tesseract PSM 11 + OEM 1 with Otsu handles coloured packaging correctly.
        try:
            import cv2
            if len(image.shape) == 3:
                proc_image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                proc_image = image
        except Exception:
            proc_image = image  # fallback: pass original array unchanged

        # PSM 11: sparse text — read text anywhere without assuming a structured layout.
        # This is essential for packaging where text is scattered, diagonal, and on curves.
        tesseract_config = "--psm 11 --oem 1"

        try:
            data: dict[str, list[Any]] = pytesseract.image_to_data(
                proc_image, output_type=pytesseract.Output.DICT, config=tesseract_config
            )
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

        # DEBUG: log what Tesseract actually read — critical for diagnosing demo-matcher misses
        logger.info(
            f"[tesseract] image={source_image_id[:8]} lines={len(lines)} avg_conf={avg_conf} "
            f"text_preview={repr(full_text[:300])}"
        )

        return OCRResult(
            source_image_id=source_image_id,
            lines=lines,
            full_text=full_text,
            average_confidence=avg_conf,
            engine_used=self.name,
        )

