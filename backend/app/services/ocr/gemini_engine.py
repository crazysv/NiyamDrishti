import json
import logging
import math
import time
from typing import Any

import cv2
import numpy as np
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.ocr.base import BaseOCREngine
from app.services.ocr.schemas import BoundingBox, OCRLine, OCRResult

logger = logging.getLogger(__name__)

GEMINI_OCR_SYSTEM_PROMPT = (
    "You are an expert OCR and packaging text recognition engine for Legal Metrology compliance inspection.\n"
    "Carefully inspect the provided packaged commodity image. Prioritize and extract every visible legally relevant "
    "declaration as its own region. Do not stop after the brand or a marketing claim. Required regions include:\n"
    "- Maximum Retail Price (MRP)\n"
    "- Net quantity / weight / volume / count / dimensions\n"
    "- Manufacturing / packaging / import dates\n"
    "- Name and address of manufacturer, packer, or importer\n"
    "- Consumer care contact details (phone, email, address)\n"
    "- Country of origin\n"
    "- Common or generic commodity name\n"
    "- Barcode numbers and batch codes\n"
    "- Product name only after the declarations above\n"
    "\n"
    "Read the complete image, including the small-print price/date/contact panel. If a declaration spans multiple "
    "printed lines, return it as one region containing all of those lines. Exclude slogans, promotional claims, and "
    "unrelated marketing copy unless they are the only visible product-name text.\n"
    "The photographed package may be sideways or upside down. Determine the orientation in which its text is upright "
    "before reading it, but report every box in the original uploaded image's [ymin, xmin, ymax, xmax] coordinates.\n"
    "\n"
    "For each detected text segment, return:\n"
    "1. 'text': The exact textual content visible on the package.\n"
    "2. 'box_2d': Bounding box as [ymin, xmin, ymax, xmax] normalized on a 0 to 1000 scale.\n"
    "3. 'confidence': Estimated legibility confidence between 0.0 and 1.0.\n"
    "Return only the structured JSON. Do NOT evaluate legal compliance."
)

GEMINI_OCR_SPARSE_RETRY_PROMPT = (
    "The previous OCR response was incomplete. A one-region result is not acceptable for this package image "
    "unless only one text fragment is legible. Reinspect the complete image at full detail and return separate "
    "regions for every readable statutory declaration, including small-print legal text, contact details, "
    "net quantity, dates, price, origin, batch/barcode, and the product name. Preserve the original-image "
    "[ymin, xmin, ymax, xmax] coordinates. Return only the structured JSON."
)


class GeminiRegionItem(BaseModel):
    """Structured text region extracted by Gemini Vision."""

    text: str = Field(..., description="Visible text string detected in the package region")
    box_2d: list[float] = Field(
        ...,
        description="2D bounding box as [ymin, xmin, ymax, xmax] normalized to 0-1000",
    )
    confidence: float = Field(
        default=0.92,
        ge=0.0,
        le=1.0,
        description="Provider-estimated confidence between 0.0 and 1.0",
    )


class GeminiOCRResponse(BaseModel):
    """Complete structured JSON schema enforced by Gemini structured output."""

    regions: list[GeminiRegionItem] = Field(
        default_factory=list,
        description="List of detected text regions with coordinates and confidence",
    )


def convert_gemini_box_to_pixels(
    box_2d: list[float | int],
    image_width: int,
    image_height: int,
) -> BoundingBox | None:
    """
    Defensively converts normalized Gemini coordinates [ymin, xmin, ymax, xmax] (0-1000 scale)
    to pixel-level BoundingBox with polygon points for the source image coordinate space.
    Clips and validates coordinates against image boundaries.
    """
    if not box_2d or len(box_2d) != 4:
        return None

    try:
        ymin, xmin, ymax, xmax = [float(v) for v in box_2d]
    except (ValueError, TypeError):
        return None

    # Defensive check against NaN / Inf
    for val in (ymin, xmin, ymax, xmax):
        if math.isnan(val) or math.isinf(val):
            return None

    # Handle inverted coordinates defensively
    if xmin > xmax:
        xmin, xmax = xmax, xmin
    if ymin > ymax:
        ymin, ymax = ymax, ymin

    # Clip to normalized 0-1000 boundary
    xmin = max(0.0, min(1000.0, xmin))
    xmax = max(0.0, min(1000.0, xmax))
    ymin = max(0.0, min(1000.0, ymin))
    ymax = max(0.0, min(1000.0, ymax))

    # Convert to pixel space
    x_px = round((xmin / 1000.0) * image_width, 1)
    y_px = round((ymin / 1000.0) * image_height, 1)
    w_px = max(1.0, round(((xmax - xmin) / 1000.0) * image_width, 1))
    h_px = max(1.0, round(((ymax - ymin) / 1000.0) * image_height, 1))

    # Bounds clipping inside the actual image dimensions
    x_px = max(0.0, min(float(image_width - 1), x_px))
    y_px = max(0.0, min(float(image_height - 1), y_px))
    w_px = max(1.0, min(float(image_width - x_px), w_px))
    h_px = max(1.0, min(float(image_height - y_px), h_px))

    polygon = [
        [x_px, y_px],
        [round(x_px + w_px, 1), y_px],
        [round(x_px + w_px, 1), round(y_px + h_px, 1)],
        [x_px, round(y_px + h_px, 1)],
    ]

    return BoundingBox(
        x=x_px,
        y=y_px,
        w=w_px,
        h=h_px,
        polygon=polygon,
    )


class GeminiOCREngine(BaseOCREngine):
    """
    Optional Google Gemini Vision OCR engine adapter with multi-key rotation pool (OCR-04, ADR-025).
    Leverages official google-genai SDK for multimodal text recognition,
    guaranteeing evidence traceability, polygon bounding boxes, confidence normalization,
    and 100% compatibility with NiyamDrishti's downstream declaration extraction.
    Supports seamless auto-rotation across a pool of API keys (e.g. 3-key rotation)
    when a key encounters quota exhaustion (429 RESOURCE_EXHAUSTED / depleted credits).
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_keys: list[str] | None = None,
        model: str | None = None,
        client: Any | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_keys = api_keys
        self.model = model or settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
        self._client = client
        self.timeout_seconds = timeout_seconds or settings.GEMINI_TIMEOUT_SECONDS or 15.0
        self.max_retries = max_retries or settings.GEMINI_MAX_RETRIES or 2
        self._current_key_idx: int = 0
        self._clients: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def api_keys(self) -> list[str]:
        """
        Returns the ordered list of available Gemini API keys in the rotation pool.
        """
        if self._api_keys is not None:
            return [k.strip() for k in self._api_keys if k and k.strip()]
        if self._api_key is not None:
            clean = self._api_key.strip()
            return [clean] if clean else []
        return settings.get_gemini_api_keys()

    @property
    def api_key(self) -> str:
        """Returns the currently active API key, or empty string if none configured."""
        keys = self.api_keys
        if not keys:
            return ""
        return keys[self._current_key_idx % len(keys)]

    @property
    def is_available(self) -> bool:
        """Returns True if Gemini is configured with credentials or mock client."""
        return self._client is not None or len(self.api_keys) > 0

    @staticmethod
    def _mask_key(key: str) -> str:
        """Safely masks an API key for logs (e.g. AQ.Ab...xQAXE)."""
        if not key or len(key) < 10:
            return "****"
        return f"{key[:6]}...{key[-5:]}"

    @staticmethod
    def _is_exhaustion_error(err: Exception) -> bool:
        """
        Detects whether an exception indicates quota exhaustion, rate limit, depleted credits,
        or a dead/leaked/denied key that should immediately trigger rotation to the next key.
        """
        err_str = str(err).lower()
        err_type = type(err).__name__.lower()
        keywords = (
            "429",
            "403",
            "401",
            "resource_exhausted",
            "resourceexhausted",
            "quota",
            "rate limit",
            "rate_limit",
            "depleted",
            "too many requests",
            "permission_denied",
            "permissiondenied",
            "denied access",
            "reported as leaked",
            "leaked",
            "invalid_argument",
            "api_key_invalid",
            "unauthorized",
        )
        if any(k in err_str for k in keywords) or any(k in err_type for k in keywords):
            return True
        status_code = getattr(err, "code", None) or getattr(err, "status_code", None)
        return status_code in (401, 403, 429)

    @staticmethod
    def _is_model_specific_quota(err: Exception) -> bool:
        """Detects if quota failure is tied to a specific model (e.g. 20 RPD cap on 3.7)."""
        err_str = str(err).lower()
        return "generaterequestsperdayperprojectpermodel" in err_str or "generate_content_free_tier_requests" in err_str

    @staticmethod
    def _is_transient_or_model_error(err: Exception) -> bool:
        """
        Detects if an error is tied to model availability (404 deprecated/not found)
        or temporary capacity issues (503 overloaded/unavailable).
        """
        err_str = str(err).lower()
        err_type = type(err).__name__.lower()
        status_code = getattr(err, "code", None) or getattr(err, "status_code", None)
        if isinstance(status_code, int) and 500 <= status_code < 600:
            return True
        return "servererror" in err_type or any(
            k in err_str
            for k in (
                "404",
                "not_found",
                "not found",
                "no longer available",
                "503",
                "unavailable",
                "overloaded",
                "internal server error",
                "service unavailable",
            )
        )

    def _get_client_for_key(self, key: str) -> Any:
        """Lazy client resolver with per-key caching."""
        if self._client is not None:
            return self._client
        if not key:
            raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY environment variable.")
        if key not in self._clients:
            try:
                from google import genai
                from google.genai import types

                # The SDK timeout is expressed in milliseconds.  Without this,
                # GEMINI_TIMEOUT_SECONDS was only configuration documentation and
                # an overloaded upstream request could hold a Render worker open
                # indefinitely.
                self._clients[key] = genai.Client(
                    api_key=key,
                    http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)),
                )
            except Exception as e:
                logger.error(f"Failed to initialize google-genai Client: {e}")
                raise RuntimeError(f"Gemini client initialization failed: {e}") from e
        return self._clients[key]

    def _get_client(self) -> Any:
        """Compatibility wrapper for active client."""
        return self._get_client_for_key(self.api_key)

    def extract(
        self,
        image: np.ndarray,
        source_image_id: str,
        instruction_override: str | None = None,
    ) -> OCRResult:
        """
        Executes Gemini Vision multimodal OCR inference on package image array.
        Enforces structured JSON response, converts normalized coordinates to source pixels,
        and constructs an OCRResult with traceable bounding boxes.
        Automatically rotates to next API key in pool if quota exhaustion occurs.
        """
        if not self.is_available:
            raise RuntimeError("Gemini OCR engine requested but no API key is configured.")

        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            raise ValueError("Invalid or empty image array supplied to GeminiOCREngine.")

        height, width = image.shape[:2]
        if height <= 0 or width <= 0:
            raise ValueError(f"Invalid image dimensions ({width}x{height})")

        # Encode image array to JPEG bytes (BGR format standard from OpenCV/pipeline)
        success, encoded_buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not success or encoded_buf is None:
            raise ValueError("Failed to encode image array to JPEG buffer.")

        jpeg_bytes = encoded_buf.tobytes()

        from google.genai import types

        # Build structured generation config
        media_resolution = {
            "low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
            "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
            "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
        }[settings.GEMINI_OCR_MEDIA_RESOLUTION]
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeminiOCRResponse,
            temperature=0.0,
            system_instruction=GEMINI_OCR_SYSTEM_PROMPT,
            max_output_tokens=settings.GEMINI_OCR_MAX_OUTPUT_TOKENS,
            media_resolution=media_resolution,
        )

        image_part = types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")
        default_prompt_text = (
            "Extract the required statutory declarations first, then the product name. "
            "Return 2D normalized bounding boxes (0-1000) and confidence for every returned region."
        )
        prompt_text = instruction_override or default_prompt_text

        t0 = time.perf_counter()
        keys_pool = self.api_keys
        total_keys = len(keys_pool)
        raw_response = None
        last_err: Exception | None = None

        # Flash-Lite is verified against the configured production key and is
        # materially more available during the current Gemini Flash capacity
        # spikes.  Keep the stronger models as fallbacks for future recovery.
        fallback_models = [
            m
            for m in ("gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.7-flash")
            if m != self.model
        ]
        candidate_models = [self.model] + fallback_models

        # Injected mock client path (used in unit tests)
        if self._client is not None and not keys_pool:
            client = self._client
            for attempt in range(1, self.max_retries + 1):
                for model_name in candidate_models:
                    try:
                        raw_response = client.models.generate_content(
                            model=model_name,
                            contents=[image_part, prompt_text],
                            config=config,
                        )
                        break
                    except Exception as e:
                        last_err = e
                        if self._is_model_specific_quota(e) or self._is_transient_or_model_error(e):
                            continue
                if raw_response is not None:
                    break
                if attempt < self.max_retries:
                    time.sleep(0.5 * attempt)
        else:
            # Multi-key rotation pool traversal
            keys_tried = 0

            while keys_tried < max(1, total_keys):
                active_idx = self._current_key_idx % total_keys
                active_key = keys_pool[active_idx]
                masked_key = self._mask_key(active_key)

                client = self._get_client_for_key(active_key)

                for attempt in range(1, self.max_retries + 1):
                    for m_idx, model_name in enumerate(candidate_models):
                        try:
                            logger.info(
                                f"Calling Gemini OCR (model={model_name}, key={masked_key} [{active_idx + 1}/{total_keys}], "
                                f"attempt={attempt}/{self.max_retries}, img_dim={width}x{height}, source_id={source_image_id})"
                            )
                            raw_response = client.models.generate_content(
                                model=model_name,
                                contents=[image_part, prompt_text],
                                config=config,
                            )
                            break
                        except Exception as e:
                            last_err = e
                            next_model = candidate_models[m_idx + 1] if m_idx + 1 < len(candidate_models) else None

                            # 1. Model-specific quota cap -> try next model on same key
                            if self._is_model_specific_quota(e) and next_model:
                                logger.warning(
                                    f"Gemini model {model_name} quota exhausted on key {masked_key}. "
                                    f"Attempting fallback to {next_model}..."
                                )
                                continue

                            # 2. Transient overload (503) or deprecated/not found (404) -> try next model on same key
                            if self._is_transient_or_model_error(e) and next_model:
                                logger.warning(
                                    f"Gemini model {model_name} returned transient/model error ({e}). "
                                    f"Attempting fallback to {next_model} on key {masked_key}..."
                                )
                                continue

                            # 3. Key-level exhaustion or permission error (401/403/429) -> rotate to next key in pool
                            if self._is_exhaustion_error(e):
                                logger.warning(
                                    f"Gemini API key {masked_key} quota exhausted, invalid, or rate-limited: {type(e).__name__} ({e}). "
                                    f"Rotating to next key in pool..."
                                )
                                break

                            logger.warning(
                                f"Gemini API request failed on attempt {attempt}/{self.max_retries} with key {masked_key} (model={model_name}): {type(e).__name__}"
                            )

                    if raw_response is not None or (last_err and self._is_exhaustion_error(last_err)):
                        break
                    if attempt < self.max_retries:
                        time.sleep(0.5 * attempt)

                if raw_response is not None:
                    break

                # Advance to next key in pool
                self._current_key_idx = (self._current_key_idx + 1) % total_keys
                keys_tried += 1

        if raw_response is None:
            logger.error(f"Gemini OCR failed completely after trying rotation pool: {last_err}")
            raise RuntimeError(f"Gemini OCR service failed (rotation pool exhausted): {last_err}") from last_err

        elapsed_sec = time.perf_counter() - t0

        def parse_structured_response(response: Any) -> GeminiOCRResponse:
            response_text = response.text
            if not response_text:
                raise ValueError("Empty response text from Gemini Vision API.")
            return GeminiOCRResponse.model_validate(json.loads(response_text))

        # Parse structured response. Gemini can occasionally satisfy the JSON
        # schema with only a brand logo, despite a declaration-rich package
        # photo. That is not a useful OCR success: retry once with an explicit
        # completeness instruction before downstream rules label every absent
        # declaration as a product violation.
        try:
            parsed_data = parse_structured_response(raw_response)
        except Exception as parse_err:
            logger.error(f"Failed to parse Gemini structured OCR output: {parse_err}")
            raise ValueError(f"Malformed Gemini OCR output: {parse_err}") from parse_err

        if len(parsed_data.regions) < 2:
            initial_region_count = len(parsed_data.regions)
            logger.warning(
                "Gemini OCR returned only %s region(s) for source_id=%s; requesting a declaration-focused retry.",
                len(parsed_data.regions),
                source_image_id,
            )
            try:
                sparse_retry_response = client.models.generate_content(
                    model=model_name,
                    contents=[image_part, GEMINI_OCR_SPARSE_RETRY_PROMPT],
                    config=config,
                )
                sparse_retry_data = parse_structured_response(sparse_retry_response)
                if len(sparse_retry_data.regions) > len(parsed_data.regions):
                    parsed_data = sparse_retry_data
                    logger.info(
                        "Gemini declaration-focused retry improved source_id=%s from %s to %s regions.",
                        source_image_id,
                        initial_region_count,
                        len(parsed_data.regions),
                    )
            except Exception as retry_err:
                # Preserve a valid initial OCR response if the optional retry
                # is unavailable; strict provider failure semantics remain in
                # effect for the original request itself.
                logger.warning("Gemini sparse OCR retry failed for source_id=%s: %s", source_image_id, retry_err)

        lines: list[OCRLine] = []
        confidences: list[float] = []

        for idx, region in enumerate(parsed_data.regions):
            clean_text = region.text.strip()
            if not clean_text:
                continue

            bbox = convert_gemini_box_to_pixels(
                region.box_2d,
                image_width=width,
                image_height=height,
            )
            if bbox is None:
                continue

            # Normalized bounded confidence
            conf_val = max(0.0, min(1.0, float(region.confidence)))
            confidences.append(conf_val)

            line = OCRLine(
                text=clean_text,
                confidence=round(conf_val, 4),
                bounding_box=bbox,
                source_image_id=source_image_id,
                engine=self.name,
                line_number=idx + 1,
            )
            lines.append(line)

        avg_conf = round(float(sum(confidences) / len(confidences)), 4) if confidences else 0.0
        full_text = "\n".join([line.text for line in lines])

        logger.info(
            f"Gemini OCR completed successfully: {len(lines)} lines detected, "
            f"avg_conf={avg_conf:.4f}, latency={elapsed_sec:.2f}s"
        )

        return OCRResult(
            source_image_id=source_image_id,
            lines=lines,
            full_text=full_text,
            average_confidence=avg_conf,
            engine_used=self.name,
            fallback_triggered=False,
        )
