from pydantic import BaseModel, Field


class CalibrationResult(BaseModel):
    """
    Result of optical scale calibration from an inspection image.
    Supports barcode known-width scale derivation and uncalibrated fallback.
    """

    is_calibrated: bool = Field(..., description="True if scale was derived from a verified standard optical reference")
    scale_mm_per_px: float | None = Field(
        default=None,
        description="Derived physical millimeter per pixel scale factor (mm/px)",
    )
    barcode_type: str | None = Field(default=None, description="Detected barcode symbology (e.g. EAN-13, EAN-8, UPC-A)")
    barcode_data: str | None = Field(default=None, description="Decoded numeric string of the barcode")
    barcode_bbox: dict[str, float] | None = Field(
        default=None, description="Bounding box of barcode in pixel coordinates {x, y, w, h}"
    )
    barcode_width_px: float | None = Field(default=None, description="Measured width of the barcode in image pixels")
    nominal_width_mm: float | None = Field(default=None, description="Nominal physical reference width in millimeters")
    method: str = Field(
        ...,
        description="Calibration methodology: 'barcode_ean13', 'barcode_ean8', 'barcode_upca', 'uncalibrated_pdp_ratio'",
    )
    warning: str | None = Field(
        default=None,
        description="Explicit warning message when measurement is uncalibrated",
    )


class MeasuredElement(BaseModel):
    """Represents a dimension measured with optical calibration metadata."""

    height_px: float
    height_mm: float | None = None
    pdp_height_ratio: float | None = None
    is_calibrated: bool
    scale_mm_per_px: float | None = None
    calibration_method: str
    warning: str | None = None
