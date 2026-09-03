from abc import ABC, abstractmethod

import numpy as np

from app.services.ocr.schemas import OCRResult


class BaseOCREngine(ABC):
    """Abstract base class for OCR engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the OCR engine."""
        pass

    @abstractmethod
    def extract(self, image: np.ndarray, source_image_id: str) -> OCRResult:
        """
        Extracts text, confidence scores, and bounding boxes from an image array.
        """
        pass
