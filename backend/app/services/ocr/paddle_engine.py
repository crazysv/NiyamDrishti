import logging
from typing import Any

import numpy as np

from app.services.ocr.base import BaseOCREngine
from app.services.ocr.schemas import BoundingBox, OCRLine, OCRResult

logger = logging.getLogger(__name__)


class PaddleOCREngine(BaseOCREngine):
    """
    PaddleOCR PP-OCR engine integration (OCR-01).
    Extracts text lines with 4-point polygon bounding boxes and confidence scores.
    """

    def __init__(self, ocr_instance: Any | None = None, lang: str = "en") -> None:
        self._ocr = ocr_instance
        self.lang = lang

    @property
    def name(self) -> str:
        return "paddleocr"

    def _get_ocr(self) -> Any:
        """Lazy loader for PaddleOCR instance to minimize startup overhead."""
        if self._ocr is None:
            try:
                import os

                # Configure low-memory flags for PaddlePaddle C++ allocator
                os.environ.setdefault("FLAGS_allocator_strategy", "naive_best_fit")
                os.environ.setdefault("FLAGS_fraction_of_gpu_memory_to_use", "0.0")
                os.environ.setdefault("FLAGS_eager_delete_tensor_gb", "0.0")

                from paddleocr import PaddleOCR

                # PP-OCR with angle classification
                self._ocr = PaddleOCR(use_angle_cls=True, lang=self.lang, show_log=False)
            except Exception as e:
                logger.error(f"Failed to initialize PaddleOCR: {e}")
                raise RuntimeError(f"PaddleOCR initialization failed: {e}") from e
        return self._ocr

    def extract(self, image: np.ndarray, source_image_id: str) -> OCRResult:
        """
        Executes PaddleOCR inference on image array.
        Output format from PaddleOCR:
        [[[box_points_4x2], (text, confidence)], ...]
        """
        ocr = self._get_ocr()
        # PaddleOCR expects RGB or BGR numpy array
        raw_result = ocr.ocr(image, cls=True)

        lines: list[OCRLine] = []
        confidences: list[float] = []

        # PaddleOCR returns a list containing lists of lines, e.g. [lines]
        if raw_result and len(raw_result) > 0 and raw_result[0] is not None:
            for idx, item in enumerate(raw_result[0]):
                if not item or len(item) != 2:
                    continue

                poly_pts, (text, conf) = item
                text_str = str(text).strip()
                if not text_str:
                    continue

                conf_float = max(0.0, min(1.0, float(conf)))
                confidences.append(conf_float)

                # Compute axis-aligned bounding box from polygon coordinates
                poly = [[float(p[0]), float(p[1])] for p in poly_pts]
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]

                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)

                bbox = BoundingBox(
                    x=round(min_x, 1),
                    y=round(min_y, 1),
                    w=round(max_x - min_x, 1),
                    h=round(max_y - min_y, 1),
                    polygon=poly,
                )

                line = OCRLine(
                    text=text_str,
                    confidence=round(conf_float, 4),
                    bounding_box=bbox,
                    source_image_id=source_image_id,
                    engine=self.name,
                    line_number=idx + 1,
                )
                lines.append(line)

        avg_conf = round(float(sum(confidences) / len(confidences)), 4) if confidences else 0.0
        full_text = "\n".join([line.text for line in lines])

        del raw_result
        import gc

        gc.collect()

        return OCRResult(
            source_image_id=source_image_id,
            lines=lines,
            full_text=full_text,
            average_confidence=avg_conf,
            engine_used=self.name,
        )
