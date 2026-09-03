from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Normalized or pixel-level bounding box with polygon support."""

    x: float = Field(..., description="Top-left X coordinate")
    y: float = Field(..., description="Top-left Y coordinate")
    w: float = Field(..., description="Width")
    h: float = Field(..., description="Height")
    polygon: list[list[float]] | None = Field(
        default=None, description="Detailed 4-point polygon [[x1, y1], [x2, y2], ...]"
    )


class OCRLine(BaseModel):
    """Represents a recognized line or chunk of text with evidence mapping metadata."""

    text: str = Field(..., description="Recognized text string")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score normalized between 0.0 and 1.0")
    bounding_box: BoundingBox = Field(..., description="Traceable bounding box in pixel coordinates")
    source_image_id: str = Field(..., description="Identifier of the source image")
    engine: str = Field(default="paddleocr", description="OCR engine that extracted this line")
    line_number: int = Field(default=0, description="Sequential line index")


class OCRResult(BaseModel):
    """Complete OCR extraction result for an image."""

    source_image_id: str = Field(..., description="Identifier of the source image")
    lines: list[OCRLine] = Field(default_factory=list, description="Extracted lines with bboxes")
    full_text: str = Field(default="", description="Concatenated extracted text separated by newlines")
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Mean confidence across all lines")
    engine_used: str = Field(default="paddleocr", description="Primary or fallback engine used")
    preprocessing_steps: list[str] = Field(default_factory=list, description="Applied preprocessing steps")
    fallback_triggered: bool = Field(default=False, description="True if fallback engine was invoked")
