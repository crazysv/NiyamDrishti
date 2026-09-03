from app.services.ocr.base import BaseOCREngine
from app.services.ocr.paddle_engine import PaddleOCREngine
from app.services.ocr.schemas import BoundingBox, OCRLine, OCRResult
from app.services.ocr.service import OCRService
from app.services.ocr.tesseract_engine import TesseractEngine

__all__ = [
    "BaseOCREngine",
    "PaddleOCREngine",
    "TesseractEngine",
    "OCRService",
    "OCRResult",
    "OCRLine",
    "BoundingBox",
]
