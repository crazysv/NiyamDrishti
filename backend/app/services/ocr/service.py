import logging

import numpy as np
from PIL import Image

from app.core.config import settings
from app.services.ocr.base import BaseOCREngine
from app.services.ocr.paddle_engine import PaddleOCREngine
from app.services.ocr.schemas import BoundingBox, OCRLine, OCRResult
from app.services.ocr.tesseract_engine import TesseractEngine
from app.services.preprocessing import PreprocessedImage, PreprocessingPipeline
from app.services.preprocessing.pipeline import map_polygon_to_original

logger = logging.getLogger(__name__)


class OCRService:
    """
    Unified OCR Service for NiyamDrishti Legal Metrology verification.
    Coordinates:
    - Primary engine: PaddleOCR PP-OCR (OCR-01)
    - Fallback engine: Tesseract 5.x (OCR-02)
    - Zero data loss: text + confidence + bounding box + source image id (OCR-03)
    - Optional cloud engine: Google Gemini Vision (OCR-04, ADR-025)
    - Inverse coordinate mapping to raw capture pixels.
    """

    def __init__(
        self,
        primary_engine: BaseOCREngine | None = None,
        fallback_engine: BaseOCREngine | None = None,
        gemini_engine: BaseOCREngine | None = None,
        min_confidence_threshold: float = 0.60,
        preprocessing_pipeline: PreprocessingPipeline | None = None,
    ) -> None:
        self.primary_engine = primary_engine or PaddleOCREngine()
        self.fallback_engine = fallback_engine or TesseractEngine()
        self._gemini_engine = gemini_engine
        self.min_confidence_threshold = min_confidence_threshold
        self.pipeline = preprocessing_pipeline or PreprocessingPipeline()
        self._custom_local_engines = primary_engine is not None or fallback_engine is not None

    @property
    def gemini_engine(self) -> BaseOCREngine:
        """Lazy loader for GeminiOCREngine."""
        if self._gemini_engine is None:
            from app.services.ocr.gemini_engine import GeminiOCREngine

            self._gemini_engine = GeminiOCREngine()
        return self._gemini_engine

    def is_gemini_available(self) -> bool:
        """Checks if Gemini Vision OCR engine is configured and ready."""
        if self._gemini_engine is not None:
            return getattr(self._gemini_engine, "is_available", True)
        from app.services.ocr.gemini_engine import GeminiOCREngine

        engine = GeminiOCREngine()
        return engine.is_available

    def _map_lines_to_original(self, lines: list[OCRLine], preprocessed: PreprocessedImage) -> list[OCRLine]:
        """
        Maps bounding boxes from preprocessed coordinate space back to original photo pixel space.
        Preserves original polygon points or transforms them if transforms were applied.
        """
        mapped_lines: list[OCRLine] = []
        for line in lines:
            processed_polygon = line.bounding_box.polygon or [
                [line.bounding_box.x, line.bounding_box.y],
                [line.bounding_box.x + line.bounding_box.w, line.bounding_box.y],
                [line.bounding_box.x + line.bounding_box.w, line.bounding_box.y + line.bounding_box.h],
                [line.bounding_box.x, line.bounding_box.y + line.bounding_box.h],
            ]
            original_polygon = map_polygon_to_original(
                processed_polygon,
                scale_factor=preprocessed.scale_factor,
                transforms=preprocessed.transforms,
                original_shape=preprocessed.original_shape,
            )
            xs = [point[0] for point in original_polygon]
            ys = [point[1] for point in original_polygon]

            orig_bbox = BoundingBox(
                x=min(xs),
                y=min(ys),
                w=max(xs) - min(xs),
                h=max(ys) - min(ys),
                polygon=original_polygon,
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
        provider: str | None = None,
    ) -> OCRResult:
        """
        Runs complete OCR flow on image:
        1. Preprocess if requested (or use existing PreprocessedImage)
        2. Determine provider routing strategy:
           - "gemini": Directly invoke Gemini Vision provider (strict; never silently changes engine)
           - "local" / "paddleocr": Default PaddleOCR with Tesseract fallback
           - "auto" / "enhanced": If Gemini is enabled and available, uses Gemini; otherwise PaddleOCR -> Tesseract
        3. Execute OCR engine(s)
        4. Map bounding boxes back to original capture coordinate space (OCR-03)
        """
        if provider:
            effective_provider = provider.lower().strip()
        elif self._custom_local_engines and self._gemini_engine is None:
            effective_provider = "local"
        else:
            effective_provider = (settings.OCR_PROVIDER or "auto").lower().strip()

        applied_steps: list[str] = []
        preprocessed: PreprocessedImage | None = None

        if isinstance(image_input, PreprocessedImage):
            preprocessed = image_input
            image_array = preprocessed.image
            applied_steps = preprocessed.applied_steps
        elif effective_provider == "gemini":
            # Gemini Vision receives the decoded source pixels directly. The
            # local OCR preprocessing pipeline includes glare inpainting and
            # perspective transforms which can erase white small-print text
            # on coloured packaging and unnecessarily complicate coordinates.
            # The browser upload is already canonicalized upright; preserving
            # these source pixels makes Gemini boxes directly traceable.
            image_array = self.pipeline.load_image(image_input)
            applied_steps = ["source_image_preserved_for_gemini"]
        elif run_preprocessing:
            preprocessed = self.pipeline.process(image_input)
            image_array = preprocessed.image
            applied_steps = preprocessed.applied_steps
        else:
            image_array = self.pipeline.load_image(image_input)

        # Strategy 1: Explicit or deployment-selected Gemini OCR.  This mode is
        # deliberately strict: a caller that selected Gemini must never receive
        # a hidden Paddle/Tesseract result, particularly on the 512 MB demo host.
        if effective_provider == "gemini":
            if self.is_gemini_available():
                try:
                    logger.info("Executing Gemini Vision OCR provider (OCR-04)")
                    gemini_result = self.gemini_engine.extract(image_array, source_image_id=source_image_id)
                    gemini_result.preprocessing_steps = applied_steps
                    if preprocessed and len(gemini_result.lines) > 0:
                        gemini_result.lines = self._map_lines_to_original(gemini_result.lines, preprocessed)
                    del image_array
                    import gc

                    gc.collect()
                    return gemini_result
                except Exception as g_err:
                    logger.error("Gemini OCR engine failed in strict Gemini mode: %s", g_err)
                    raise RuntimeError(f"Gemini OCR failed: {g_err}") from g_err
            else:
                raise RuntimeError("Gemini OCR was selected but no Gemini API key is configured.")

        # Strategy 2: Auto / Enhanced Mode with Gemini Enabled
        # For presentation accuracy or when explicitly enabled in environment
        elif (
            effective_provider in ("auto", "enhanced")
            and (settings.GEMINI_ENABLED or settings.OCR_PROVIDER == "gemini")
            and self.is_gemini_available()
        ):
            try:
                logger.info("Executing Gemini Vision OCR under enhanced/presentation configuration")
                gemini_result = self.gemini_engine.extract(image_array, source_image_id=source_image_id)
                if len(gemini_result.lines) > 0:
                    gemini_result.preprocessing_steps = applied_steps
                    if preprocessed:
                        gemini_result.lines = self._map_lines_to_original(gemini_result.lines, preprocessed)
                    del image_array
                    import gc

                    gc.collect()
                    return gemini_result
            except Exception as g_err:
                logger.warning(f"Enhanced Gemini OCR attempt failed: {g_err}. Reverting to local PaddleOCR.")

        # Standard Local OCR Pipeline (PaddleOCR Primary -> Tesseract Fallback)
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
            del image_array
            import gc

            gc.collect()
            return primary_result

        # Optional Gemini rescue if primary failed/low confidence and Gemini is available (Strategy B: Enhanced mode)
        if (
            not primary_success
            and effective_provider in ("auto", "enhanced")
            and self.is_gemini_available()
            and (settings.GEMINI_ENABLED or bool(settings.GEMINI_API_KEY))
        ):
            try:
                logger.info("Triggering Gemini Vision to rescue low-confidence/failed local OCR result")
                rescue_result = self.gemini_engine.extract(image_array, source_image_id=source_image_id)
                if len(rescue_result.lines) > 0:
                    rescue_result.preprocessing_steps = applied_steps
                    rescue_result.fallback_triggered = True
                    if preprocessed:
                        rescue_result.lines = self._map_lines_to_original(rescue_result.lines, preprocessed)
                    del image_array
                    import gc

                    gc.collect()
                    return rescue_result
            except Exception as rescue_err:
                logger.warning(f"Gemini rescue attempt failed: {rescue_err}. Continuing to Tesseract.")

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

        del image_array
        import gc

        gc.collect()

        return chosen_result
