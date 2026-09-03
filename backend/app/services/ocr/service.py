import logging

import numpy as np
from PIL import Image

from app.services.ocr.base import BaseOCREngine
from app.services.ocr.paddle_engine import PaddleOCREngine
from app.services.ocr.schemas import BoundingBox, OCRLine, OCRResult
from app.services.ocr.tesseract_engine import TesseractEngine
from app.services.preprocessing import PreprocessedImage, PreprocessingPipeline
from app.services.preprocessing.pipeline import map_bbox_to_original

logger = logging.getLogger(__name__)


class OCRService:
    """
    Unified OCR Service for NiyamDrishti Legal Metrology verification.
    Coordinates:
    - Primary engine: PaddleOCR PP-OCR (OCR-01)
    - Fallback engine: Tesseract 5.x (OCR-02)
    - Zero data loss: text + confidence + bounding box + source image id (OCR-03)
    - Inverse coordinate mapping to raw capture pixels.
    """

    def __init__(
        self,
        primary_engine: BaseOCREngine | None = None,
        fallback_engine: BaseOCREngine | None = None,
        min_confidence_threshold: float = 0.60,
        preprocessing_pipeline: PreprocessingPipeline | None = None,
    ) -> None:
        self.primary_engine = primary_engine or PaddleOCREngine()
        self.fallback_engine = fallback_engine or TesseractEngine()
        self.min_confidence_threshold = min_confidence_threshold
        self.pipeline = preprocessing_pipeline or PreprocessingPipeline()

    def _map_lines_to_original(self, lines: list[OCRLine], preprocessed: PreprocessedImage) -> list[OCRLine]:
        """
        Maps bounding boxes from preprocessed coordinate space back to original photo pixel space.
        Preserves original polygon points or transforms them if transforms were applied.
        """
        mapped_lines: list[OCRLine] = []
        for line in lines:
            orig_box_dict = map_bbox_to_original(
                {
                    "x": line.bounding_box.x,
                    "y": line.bounding_box.y,
                    "w": line.bounding_box.w,
                    "h": line.bounding_box.h,
                },
                scale_factor=preprocessed.scale_factor,
                transforms=preprocessed.transforms,
            )

            orig_bbox = BoundingBox(
                x=orig_box_dict["x"],
                y=orig_box_dict["y"],
                w=orig_box_dict["w"],
                h=orig_box_dict["h"],
                polygon=line.bounding_box.polygon,
            )

            mapped_lines.append(
                OCRLine(
                    text=line.text,
                    confidence=line.confidence,
                    bounding_box=orig_bbox,
                    source_image_id=line.source_image_id,
                    engine=line.engine,
                    line_number=line.line_number,
                )
            )
        return mapped_lines

    def process_image(
        self,
        image_input: bytes | str | np.ndarray | Image.Image | PreprocessedImage,
        source_image_id: str,
        run_preprocessing: bool = True,
    ) -> OCRResult:
        """
        Runs complete OCR flow on image:
        1. Preprocess if requested (or use existing PreprocessedImage)
        2. Execute primary engine (PaddleOCR)
        3. Check confidence: if below threshold or fails, run fallback engine (Tesseract)
        4. Map bounding boxes back to original capture coordinate space (OCR-03)
        """
        applied_steps: list[str] = []
        preprocessed: PreprocessedImage | None = None

        if isinstance(image_input, PreprocessedImage):
            preprocessed = image_input
            image_array = preprocessed.image
            applied_steps = preprocessed.applied_steps
        elif run_preprocessing:
            preprocessed = self.pipeline.process(image_input)
            image_array = preprocessed.image
            applied_steps = preprocessed.applied_steps
        else:
            image_array = self.pipeline.load_image(image_input)

        primary_success = False
        primary_result: OCRResult | None = None

        # 1. Primary Engine Attempt (PaddleOCR)
        try:
            primary_result = self.primary_engine.extract(image_array, source_image_id=source_image_id)
            primary_result.preprocessing_steps = applied_steps
            # Check if primary result is satisfactory
            if len(primary_result.lines) > 0 and primary_result.average_confidence >= self.min_confidence_threshold:
                primary_success = True
            else:
                logger.info(
                    f"Primary OCR confidence ({primary_result.average_confidence:.2f}) "
                    f"is below threshold ({self.min_confidence_threshold:.2f}). Triggering fallback."
                )
        except Exception as e:
            logger.warning(f"Primary OCR engine ({self.primary_engine.name}) failed: {e}")

        # 2. Return primary if strong and successful
        if primary_success and primary_result is not None:
            if preprocessed:
                primary_result.lines = self._map_lines_to_original(primary_result.lines, preprocessed)
            return primary_result

        # 3. Fallback Engine Attempt (Tesseract)
        fallback_result: OCRResult | None = None
        try:
            logger.info(f"Invoking fallback OCR engine: {self.fallback_engine.name}")
            fallback_result = self.fallback_engine.extract(image_array, source_image_id=source_image_id)
            fallback_result.preprocessing_steps = applied_steps
            fallback_result.fallback_triggered = True
        except Exception as e:
            logger.warning(f"Fallback OCR engine ({self.fallback_engine.name}) failed: {e}")

        # 4. Choose best available result
        chosen_result: OCRResult
        if fallback_result and len(fallback_result.lines) > 0:
            if (
                primary_result
                and len(primary_result.lines) > 0
                and primary_result.average_confidence > fallback_result.average_confidence
            ):
                chosen_result = primary_result
            else:
                chosen_result = fallback_result
        elif primary_result:
            chosen_result = primary_result
        else:
            # Empty result if both failed
            chosen_result = OCRResult(
                source_image_id=source_image_id,
                lines=[],
                full_text="",
                average_confidence=0.0,
                engine_used="none",
                preprocessing_steps=applied_steps,
                fallback_triggered=True,
            )

        # 5. Map coordinates back to original image space
        if preprocessed and len(chosen_result.lines) > 0:
            chosen_result.lines = self._map_lines_to_original(chosen_result.lines, preprocessed)

        return chosen_result
