import math
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class BoundingBox(BaseModel):
    """Engine-neutral OCR region in the stored source image's pixel space.

    ``polygon`` is always a clockwise quadrilateral and ``x/y/w/h`` is its
    enclosing axis-aligned rectangle.  Engines may have very different native
    coordinate formats, but no caller downstream of OCR has to know that.
    """

    x: float = Field(..., description="Top-left X coordinate")
    y: float = Field(..., description="Top-left Y coordinate")
    w: float = Field(..., description="Width")
    h: float = Field(..., description="Height")
    polygon: list[list[float]] | None = Field(
        default=None, description="Clockwise source-pixel quadrilateral [[x1, y1], ...]"
    )
    coordinate_space: Literal["source_image_px"] = Field(
        default="source_image_px", description="Coordinates refer to the persisted, upright source image."
    )

    @model_validator(mode="after")
    def complete_polygon(self) -> "BoundingBox":
        if self.w <= 0 or self.h <= 0:
            raise ValueError("OCR bounding boxes must have positive width and height")
        if self.polygon is None:
            self.polygon = [
                [self.x, self.y],
                [self.x + self.w, self.y],
                [self.x + self.w, self.y + self.h],
                [self.x, self.y + self.h],
            ]
        if len(self.polygon) != 4 or any(len(point) != 2 for point in self.polygon):
            raise ValueError("OCR bounding box polygon must contain exactly four [x, y] points")
        points = [[float(point[0]), float(point[1])] for point in self.polygon]
        center_x = sum(point[0] for point in points) / 4
        center_y = sum(point[1] for point in points) / 4
        # In image coordinates (positive y down), ascending atan2 yields a
        # clockwise winding. Rotate the list so consumers always start at TL.
        points.sort(key=lambda point: math.atan2(point[1] - center_y, point[0] - center_x))
        top_left_index = min(range(4), key=lambda index: (points[index][1], points[index][0]))
        self.polygon = points[top_left_index:] + points[:top_left_index]
        xs = [point[0] for point in self.polygon]
        ys = [point[1] for point in self.polygon]
        self.x = min(xs)
        self.y = min(ys)
        self.w = max(xs) - self.x
        self.h = max(ys) - self.y
        return self


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
