import logging
import uuid

import numpy as np
from PIL import Image
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import InspectionImage
from app.services.calibration.detector import BarcodeCalibrationDetector
from app.services.calibration.schemas import CalibrationResult, MeasuredElement
from app.services.preprocessing import PreprocessedImage, PreprocessingPipeline

logger = logging.getLogger(__name__)


class OpticalCalibrationService:
    """
    Coordinates optical scale calibration, dimension measurement, and database persistence (CAL-01, CAL-02, CAL-03).
    """

    def __init__(
        self,
        detector: BarcodeCalibrationDetector | None = None,
        preprocessing_pipeline: PreprocessingPipeline | None = None,
    ) -> None:
        self.detector = detector or BarcodeCalibrationDetector()
        self.pipeline = preprocessing_pipeline or PreprocessingPipeline()

    def calibrate_image(
        self, image_input: bytes | str | np.ndarray | Image.Image | PreprocessedImage
    ) -> CalibrationResult:
        """Runs barcode detection and derives optical scale on the image."""
        if isinstance(image_input, PreprocessedImage):
            image_array = image_input.image
        elif isinstance(image_input, np.ndarray):
            image_array = image_input
        else:
            image_array = self.pipeline.load_image(image_input)

        return self.detector.calibrate(image_array)

    def measure_dimension(
        self,
        height_px: float,
        pdp_height_px: float,
        calibration: CalibrationResult,
    ) -> MeasuredElement:
        """
        Measures font or element dimension using derived optical calibration.
        If calibrated: computes physical height in millimeters.
        If uncalibrated (CAL-03): computes relative PDP-height ratio and sets explicit warning.
        """
        pdp_ratio = round(float(height_px / pdp_height_px), 4) if pdp_height_px > 0 else None

        if calibration.is_calibrated and calibration.scale_mm_per_px is not None:
            height_mm = round(float(height_px * calibration.scale_mm_per_px), 2)
            return MeasuredElement(
                height_px=height_px,
                height_mm=height_mm,
                pdp_height_ratio=pdp_ratio,
                is_calibrated=True,
                scale_mm_per_px=calibration.scale_mm_per_px,
                calibration_method=calibration.method,
                warning=None,
            )

        # Uncalibrated Fallback Path (CAL-03)
        return MeasuredElement(
            height_px=height_px,
            height_mm=None,
            pdp_height_ratio=pdp_ratio,
            is_calibrated=False,
            scale_mm_per_px=None,
            calibration_method=calibration.method,
            warning=calibration.warning or "Uncalibrated measurement: no reference barcode detected.",
        )

    async def persist_calibration(
        self,
        db: AsyncSession,
        image_id: uuid.UUID,
        calibration: CalibrationResult,
    ) -> None:
        """
        Persists derived mm-per-pixel scale to inspection_images table (CAL-02).
        """
        stmt = (
            update(InspectionImage)
            .where(InspectionImage.id == image_id)
            .values(calibration_scale_mm_per_px=calibration.scale_mm_per_px)
        )
        await db.execute(stmt)
        await db.commit()
