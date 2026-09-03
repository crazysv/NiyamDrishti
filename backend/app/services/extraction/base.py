from abc import ABC, abstractmethod

from app.services.extraction.schemas import ExtractedDeclaration
from app.services.ocr.schemas import OCRLine


class BaseFieldExtractor(ABC):
    """Abstract base class for Legal Metrology declaration extractors."""

    @property
    @abstractmethod
    def field_type(self) -> str:
        """The field type this extractor is responsible for."""
        pass

    @abstractmethod
    def extract(self, lines: list[OCRLine], source_image_id: str) -> list[ExtractedDeclaration]:
        """
        Extracts zero or more declaration instances of field_type from OCR lines.
        """
        pass
