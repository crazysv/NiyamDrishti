from dataclasses import dataclass


@dataclass
class PipelineConfig:
    """Configuration options for the preprocessing pipeline."""

    # Dimension constraints (constrained to 1280 to prevent Render 512MB RAM OOM)
    max_dimension: int = 1280
    min_dimension: int = 600

    # Denoising configuration (edge-preserving)
    enable_denoise: bool = True
    bilateral_diameter: int = 7
    bilateral_sigma_color: float = 50.0
    bilateral_sigma_space: float = 50.0

    # Contrast adjustment configuration (CLAHE)
    enable_contrast: bool = True
    clahe_clip_limit: float = 2.0
    clahe_tile_grid_size: tuple[int, int] = (8, 8)

    # Perspective & Deskew configuration (PRE-02)
    enable_deskew: bool = True
    max_deskew_angle: float = 45.0
    enable_perspective_correction: bool = True
    min_quad_area_ratio: float = 0.20

    # Glare suppression configuration (PRE-03)
    enable_glare_suppression: bool = True
    glare_luminance_threshold: int = 240
    glare_saturation_threshold: int = 40
    glare_inpaint_radius: int = 3

    # Text-region enhancement configuration (PRE-03)
    enable_text_enhancement: bool = True
    text_unsharp_amount: float = 0.6
    text_unsharp_sigma: float = 1.0
