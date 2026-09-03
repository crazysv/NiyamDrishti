import base64
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.services.preprocessing.config import PipelineConfig


@dataclass
class PreprocessedImage:
    """Represents the output of the image preprocessing pipeline."""

    image: np.ndarray  # BGR format standard in OpenCV
    original_shape: tuple[int, int]  # (height, width)
    processed_shape: tuple[int, int]  # (height, width)
    scale_factor: float  # processed_dim / original_dim
    applied_steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    transforms: list[dict[str, Any]] = field(default_factory=list)

    def to_pil(self) -> Image.Image:
        """Converts BGR numpy image to PIL Image (RGB)."""
        rgb = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def to_bytes(self, format: str = "JPEG", quality: int = 95) -> bytes:
        """Encodes preprocessed image to byte buffer."""
        pil_img = self.to_pil()
        buffer = io.BytesIO()
        pil_img.save(buffer, format=format, quality=quality)
        return buffer.getvalue()

    def to_rgb_array(self) -> np.ndarray:
        """Returns the image as an RGB numpy array (standard for PaddleOCR/models)."""
        return cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)


class PreprocessingPipeline:
    """
    Standardized image preprocessing pipeline for legal metrology label analysis.
    Implements: Resize/Normalize -> Glare Suppression -> Perspective Correction ->
    Deskew -> Denoise -> CLAHE Contrast -> Text-Region Enhancement.
    """

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()

    def load_image(self, image_input: bytes | str | Path | np.ndarray | Image.Image) -> np.ndarray:
        """Loads varied image input types into standard BGR numpy array."""
        if isinstance(image_input, np.ndarray):
            if len(image_input.shape) == 2:  # Grayscale
                return cv2.cvtColor(image_input, cv2.COLOR_GRAY2BGR)
            return image_input.copy()

        if isinstance(image_input, Image.Image):
            rgb = np.array(image_input.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        if isinstance(image_input, (str, Path)):
            path_str = str(image_input)
            if path_str.startswith("data:image"):
                # Base64 data URL
                _, encoded = path_str.split(",", 1)
                raw_bytes = base64.b64decode(encoded)
                nparr = np.frombuffer(raw_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    raise ValueError("Failed to decode base64 image data")
                return img

            img = cv2.imread(path_str, cv2.IMREAD_COLOR)
            if img is None:
                raise FileNotFoundError(f"Could not load image from path: {path_str}")
            return img

        if isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Failed to decode raw image bytes")
            return img

        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    def resize_and_normalize(self, image: np.ndarray) -> tuple[np.ndarray, float, bool]:
        """
        Resizes the image to adhere to min_dimension and max_dimension constraints
        while strictly preserving original aspect ratio.
        """
        h, w = image.shape[:2]
        max_dim = max(h, w)
        min_dim = min(h, w)
        scale = 1.0

        if max_dim > self.config.max_dimension:
            scale = self.config.max_dimension / float(max_dim)
            new_w = int(round(w * scale))
            new_h = int(round(h * scale))
            resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
            return resized, scale, True

        if min_dim < self.config.min_dimension and max_dim < self.config.max_dimension:
            scale = self.config.min_dimension / float(min_dim)
            new_w = int(round(w * scale))
            new_h = int(round(h * scale))
            resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            return resized, scale, True

        return image, 1.0, False

    def suppress_glare(self, image: np.ndarray) -> tuple[np.ndarray, bool]:
        """
        Identifies specular reflections on glossy or metallic packaging labels
        and applies inpainting to suppress glare hotspots.
        """
        hls = cv2.cvtColor(image, cv2.COLOR_BGR2HLS)
        _, l_chan, s_chan = cv2.split(hls)

        # Specular glare is characterized by very high luminance and low color saturation
        glare_mask = (l_chan >= self.config.glare_luminance_threshold) & (
            s_chan <= self.config.glare_saturation_threshold
        )
        glare_mask = glare_mask.astype(np.uint8) * 255

        # Dilate mask slightly to capture bright glare halos
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dilated_mask = cv2.dilate(glare_mask, kernel, iterations=1)

        total_pixels = image.shape[0] * image.shape[1]
        glare_pixels = int(cv2.countNonZero(dilated_mask))
        glare_ratio = glare_pixels / float(total_pixels)

        # Only apply inpainting if glare is present but not washing out the entire image
        if 0.0005 <= glare_ratio <= 0.30:
            inpainted = cv2.inpaint(
                image,
                dilated_mask,
                inpaintRadius=self.config.glare_inpaint_radius,
                flags=cv2.INPAINT_TELEA,
            )
            return inpainted, True

        return image, False

    def order_points(self, pts: np.ndarray) -> np.ndarray:
        """Orders 4 coordinates: top-left, top-right, bottom-right, bottom-left."""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def correct_perspective(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray | None, bool]:
        """
        Detects quadrilateral label/panel border and applies 4-point perspective warp.
        Returns (transformed_image, perspective_matrix, was_corrected).
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)

        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        img_area = image.shape[0] * image.shape[1]

        # Sort contours by area descending
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for c in contours[:5]:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)

            # If quadrilateral with substantial area and convex
            if len(approx) == 4 and cv2.isContourConvex(approx):
                area = cv2.contourArea(approx)
                if area >= img_area * self.config.min_quad_area_ratio:
                    pts = approx.reshape(4, 2)
                    rect = self.order_points(pts)
                    tl, tr, br, bl = rect

                    # Compute dimensions of new warped image
                    width_a = np.linalg.norm(br - bl)
                    width_b = np.linalg.norm(tr - tl)
                    max_width = max(int(width_a), int(width_b))

                    height_a = np.linalg.norm(tr - br)
                    height_b = np.linalg.norm(tl - bl)
                    max_height = max(int(height_a), int(height_b))

                    if max_width < 100 or max_height < 100:
                        continue

                    dst = np.array(
                        [
                            [0, 0],
                            [max_width - 1, 0],
                            [max_width - 1, max_height - 1],
                            [0, max_height - 1],
                        ],
                        dtype=np.float32,
                    )

                    m = cv2.getPerspectiveTransform(rect, dst)
                    warped = cv2.warpPerspective(
                        image,
                        m,
                        (max_width, max_height),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE,
                    )
                    return warped, m, True

        return image, None, False

    def detect_skew_angle(self, image: np.ndarray) -> float:
        """
        Estimates text skew angle in degrees using minAreaRect on high-density text contours.
        Returns angle in range [-max_deskew_angle, max_deskew_angle].
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

        # Dilate horizontally to merge letters into text lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=1)

        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        angles: list[float] = []

        for c in contours:
            area = cv2.contourArea(c)
            if area < 150:
                continue

            rect = cv2.minAreaRect(c)
            (w, h) = rect[1]
            a = rect[2]

            # In OpenCV 4.5+, minAreaRect returns angle in [0, 90).
            # Determine angle of the dominant orientation axis:
            skew = -(a - 90.0) if w < h else -a

            if abs(skew) <= self.config.max_deskew_angle and abs(skew) >= 0.5:
                angles.append(skew)

        if not angles:
            return 0.0

        return float(np.median(angles))

    def deskew(self, image: np.ndarray) -> tuple[np.ndarray, float, np.ndarray | None]:
        """
        Detects and corrects skew by rotating the image to level text lines.
        Returns (deskewed_image, angle, rotation_matrix).
        """
        angle = self.detect_skew_angle(image)
        if abs(angle) < 0.5 or abs(angle) > self.config.max_deskew_angle:
            return image, 0.0, None

        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        # To cancel the tilt, rotate by -angle
        rot_mat = cv2.getRotationMatrix2D(center, -angle, 1.0)
        deskewed = cv2.warpAffine(
            image,
            rot_mat,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return deskewed, angle, rot_mat

    def denoise(self, image: np.ndarray) -> np.ndarray:
        """
        Edge-preserving smoothing using Bilateral Filter.
        Removes sensor grain while keeping high-frequency stroke edges sharp for OCR.
        """
        return cv2.bilateralFilter(
            image,
            d=self.config.bilateral_diameter,
            sigmaColor=self.config.bilateral_sigma_color,
            sigmaSpace=self.config.bilateral_sigma_space,
        )

    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Enhances local contrast using CLAHE on the L (Luminance) channel of the LAB color space.
        Improves readability of faint, low-contrast, or shadow-affected label text.
        """
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=self.config.clahe_clip_limit,
            tileGridSize=self.config.clahe_tile_grid_size,
        )
        enhanced_l = clahe.apply(l_channel)

        merged_lab = cv2.merge([enhanced_l, a_channel, b_channel])
        return cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)

    def enhance_text_regions(self, image: np.ndarray) -> np.ndarray:
        """
        Sharpens text stroke edges using an unsharp mask filter to maximize OCR character clarity.
        """
        gaussian = cv2.GaussianBlur(image, (0, 0), self.config.text_unsharp_sigma)
        unsharp = cv2.addWeighted(
            image,
            1.0 + self.config.text_unsharp_amount,
            gaussian,
            -self.config.text_unsharp_amount,
            0,
        )
        return unsharp

    def process(self, image_input: bytes | str | Path | np.ndarray | Image.Image) -> PreprocessedImage:
        """
        Runs the full preprocessing pipeline on the input image.
        Execution order: Resize -> Glare Suppression -> Perspective -> Deskew -> Denoise -> Contrast -> Text Enhancement.
        """
        original = self.load_image(image_input)
        orig_h, orig_w = original.shape[:2]

        current = original
        applied_steps: list[str] = []
        transforms: list[dict[str, Any]] = []

        # 1. Resize & Normalize
        resized, scale_factor, was_resized = self.resize_and_normalize(current)
        if was_resized:
            applied_steps.append(f"resize_scale_{scale_factor:.4f}")
            transforms.append({"type": "resize", "scale": scale_factor})
            current = resized

        # 2. Glare Suppression (PRE-03)
        if self.config.enable_glare_suppression:
            suppressed, had_glare = self.suppress_glare(current)
            if had_glare:
                applied_steps.append("glare_suppression")
                current = suppressed

        # 3. Perspective Correction (PRE-02)
        if self.config.enable_perspective_correction:
            warped, p_matrix, was_warped = self.correct_perspective(current)
            if was_warped and p_matrix is not None:
                applied_steps.append("perspective_correction")
                transforms.append({"type": "perspective", "matrix": p_matrix.tolist()})
                current = warped

        # 4. Deskew (PRE-02)
        skew_angle = 0.0
        if self.config.enable_deskew:
            deskewed, angle, rot_mat = self.deskew(current)
            if abs(angle) >= 0.5 and rot_mat is not None:
                skew_angle = angle
                applied_steps.append(f"deskew_angle_{angle:+.2f}")
                transforms.append(
                    {
                        "type": "rotation",
                        "angle": angle,
                        "matrix": rot_mat.tolist(),
                    }
                )
                current = deskewed

        # 5. Edge-Preserving Denoise
        if self.config.enable_denoise:
            current = self.denoise(current)
            applied_steps.append("bilateral_denoise")

        # 6. CLAHE Contrast Adjustment
        if self.config.enable_contrast:
            current = self.enhance_contrast(current)
            applied_steps.append("clahe_contrast_enhancement")

        # 7. Text-Region Enhancement (PRE-03)
        if self.config.enable_text_enhancement:
            current = self.enhance_text_regions(current)
            applied_steps.append("text_region_enhancement")

        proc_h, proc_w = current.shape[:2]

        return PreprocessedImage(
            image=current,
            original_shape=(orig_h, orig_w),
            processed_shape=(proc_h, proc_w),
            scale_factor=scale_factor,
            applied_steps=applied_steps,
            transforms=transforms,
            metadata={
                "orig_width": orig_w,
                "orig_height": orig_h,
                "proc_width": proc_w,
                "proc_height": proc_h,
                "skew_angle": skew_angle,
            },
        )


def map_point_to_original(x: float, y: float, transforms: list[dict[str, Any]]) -> tuple[float, float]:
    """
    Applies the inverse sequence of pipeline transformations to map a point (x, y)
    from preprocessed image coordinates back to the original image coordinate space.
    """
    pt = np.array([[[x, y]]], dtype=np.float32)

    # Reverse transformation stack
    for t in reversed(transforms):
        t_type = t["type"]
        if t_type == "rotation":
            rot_mat = np.array(t["matrix"], dtype=np.float32)
            inv_rot = cv2.invertAffineTransform(rot_mat)
            pt = cv2.transform(pt, inv_rot)
        elif t_type == "perspective":
            p_mat = np.array(t["matrix"], dtype=np.float32)
            inv_p = np.linalg.inv(p_mat)
            pt = cv2.perspectiveTransform(pt, inv_p)
        elif t_type == "resize":
            scale = t["scale"]
            pt = pt * (1.0 / scale)

    mapped_x, mapped_y = pt[0, 0]
    return float(mapped_x), float(mapped_y)


def map_bbox_to_original(
    box: dict[str, float],
    scale_factor: float,
    transforms: list[dict[str, Any]] | None = None,
    round_digits: int = 1,
) -> dict[str, float]:
    """
    Translates a bounding box {"x":, "y":, "w":, "h":} from preprocessed coordinates
    back to original captured image coordinate space, accounting for scale, rotation, and perspective.
    """
    if transforms:
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        corners = [
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h),
        ]
        mapped_corners = [map_point_to_original(cx, cy, transforms) for cx, cy in corners]
        xs = [c[0] for c in mapped_corners]
        ys = [c[1] for c in mapped_corners]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        return {
            "x": round(min_x, round_digits),
            "y": round(min_y, round_digits),
            "w": round(max_x - min_x, round_digits),
            "h": round(max_y - min_y, round_digits),
        }

    if scale_factor <= 0:
        raise ValueError(f"scale_factor must be positive, got {scale_factor}")

    inv_scale = 1.0 / scale_factor
    return {
        "x": round(box["x"] * inv_scale, round_digits),
        "y": round(box["y"] * inv_scale, round_digits),
        "w": round(box["w"] * inv_scale, round_digits),
        "h": round(box["h"] * inv_scale, round_digits),
    }
