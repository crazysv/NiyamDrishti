import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import get_field_confidence_threshold
from app.services.rules.schemas import (
    EvaluationSummary,
    RuleDefinition,
    RuleEvaluationResult,
    RulePackSchema,
    VerdictType,
)

logger = logging.getLogger(__name__)

CORE_RULE_PACK_V1_PATH = Path(__file__).parent / "core_pack_v1.json"


def load_default_rule_pack() -> RulePackSchema:
    """Loads and validates the v1 core rule pack from disk."""
    with open(CORE_RULE_PACK_V1_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return RulePackSchema(**data)


class RuleEngine:
    """
    Regulatory Rule Engine (RULE-04).
    Dispatches and evaluates extracted package declarations against versioned Rule Packs.
    Decoupled from hardcoded code logic per MASTER_CONTENT.md §4.5 / 06_SCHEMA.md §3.
    """

    def __init__(self, default_pack: RulePackSchema | None = None) -> None:
        self.default_pack = default_pack or load_default_rule_pack()

    def parse_rule_pack(self, raw_pack: Any) -> RulePackSchema:
        """Parses a dictionary, DB model, or JSON object into a validated RulePackSchema."""
        if isinstance(raw_pack, RulePackSchema):
            return raw_pack
        if hasattr(raw_pack, "rules_json") and isinstance(raw_pack.rules_json, dict):
            return RulePackSchema(**raw_pack.rules_json)
        if isinstance(raw_pack, dict):
            return RulePackSchema(**raw_pack)
        raise ValueError(f"Unsupported rule pack input type: {type(raw_pack)}")

    def _determine_target_font_threshold(self, pdp_area_cm2: float, thresholds: dict[str, float]) -> float:
        """Looks up Rule 7 font-height threshold (in mm) based on PDP area."""
        if pdp_area_cm2 <= 50:
            return float(thresholds.get("50", 1.0))
        if pdp_area_cm2 <= 100:
            return float(thresholds.get("100", 1.5))
        if pdp_area_cm2 <= 500:
            return float(thresholds.get("500", 2.0))
        if pdp_area_cm2 <= 2500:
            return float(thresholds.get("2500", 4.0))
        return float(thresholds.get("gt_2500", 6.0))

    def evaluate_rules(
        self,
        fields: list[Any],
        images: list[Any] | None = None,
        commodity_category: str | None = None,
        rule_pack: RulePackSchema | dict | Any | None = None,
    ) -> EvaluationSummary:
        """
        Evaluates extracted fields and images against the active/specified rule pack.
        """
        active_pack = self.parse_rule_pack(rule_pack) if rule_pack else self.default_pack
        images = images or []

        # Map fields by field_type (e.g. 'mrp', 'net_quantity')
        field_map: dict[str, Any] = {}
        for f in fields:
            ftype = getattr(f, "field_type", None) or (f.get("field_type") if isinstance(f, dict) else None)
            if ftype and ftype not in field_map:
                field_map[ftype] = f

        # Find primary front PDP image for calibration and dimensions
        front_img = None
        for img in images:
            role = getattr(img, "image_role", None) or (img.get("image_role") if isinstance(img, dict) else None)
            if role == "front_pdp":
                front_img = img
                break
        if front_img is None and len(images) > 0:
            front_img = images[0]

        calib_scale: float | None = None
        pdp_width_px = 1200.0
        pdp_height_px = 1600.0

        if front_img is not None:
            scale_val = getattr(front_img, "calibration_scale_mm_per_px", None)
            if scale_val is None and isinstance(front_img, dict):
                scale_val = front_img.get("calibration_scale_mm_per_px")
            if scale_val is not None:
                try:
                    calib_scale = float(scale_val)
                except (ValueError, TypeError):
                    calib_scale = None

            w_val = getattr(front_img, "width_px", None) or (
                front_img.get("width_px") if isinstance(front_img, dict) else None
            )
            h_val = getattr(front_img, "height_px", None) or (
                front_img.get("height_px") if isinstance(front_img, dict) else None
            )
            if w_val:
                pdp_width_px = float(w_val)
            if h_val:
                pdp_height_px = float(h_val)

        results: list[RuleEvaluationResult] = []
        category = commodity_category or "general"

        for rule in active_pack.rules:
            # Check applicability
            applies = "all" in rule.applies_to or category in rule.applies_to
            if not applies:
                continue

            # Dispatch by rule type
            if rule.type == "field_required":
                res = self._evaluate_field_required(rule, field_map)
                results.append(res)

            elif rule.type in ("font_height_by_pdp_area", "font_height_blown_embossed"):
                res = self._evaluate_font_height(
                    rule=rule,
                    field_map=field_map,
                    calib_scale=calib_scale,
                    pdp_width_px=pdp_width_px,
                    pdp_height_px=pdp_height_px,
                )
                results.append(res)

            elif rule.type == "legibility_contrast":
                res = self._evaluate_legibility_contrast(rule, field_map)
                results.append(res)

        # Determine overall verdict
        has_fail = any(r.verdict == "fail" for r in results)
        has_review = any(r.verdict == "needs_review" for r in results)

        if has_fail:
            overall_status: VerdictType = "fail"
        elif has_review:
            overall_status = "needs_review"
        else:
            overall_status = "pass"

        # Generate violations list (ready for DB insertion into violations table)
        violations: list[dict] = []
        for r in results:
            if r.verdict in ("fail", "needs_review"):
                violations.append(
                    {
                        "rule_id": r.rule_id,
                        "rule_pack_version": active_pack.rule_pack_version,
                        "extracted_field_id": r.field_id,
                        "description": r.description,
                        "citation": r.citation,
                        "severity": r.severity,
                    }
                )

        return EvaluationSummary(
            overall_status=overall_status,
            rule_pack_version=active_pack.rule_pack_version,
            results=results,
            violations=violations,
        )

    def _evaluate_field_required(
        self,
        rule: RuleDefinition,
        field_map: dict[str, Any],
    ) -> RuleEvaluationResult:
        field_name = rule.field or "unknown"
        field_obj = field_map.get(field_name)

        if field_obj is None:
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                verdict="fail",
                field_id=None,
                field_type=field_name,
                description=f"Mandatory declaration '{field_name}' is missing from package.",
                citation=rule.citation,
                severity=rule.severity,
                bounding_box=None,
                is_calibrated=True,
                warning=None,
            )

        # Field is present
        if isinstance(field_obj, dict):
            fid = field_obj.get("id")
            bbox = field_obj.get("bounding_box")
            field_verdict = field_obj.get("verdict", "pass")
            confidence = float(field_obj.get("confidence", 1.0))
            reviewed = bool(field_obj.get("reviewed_by_officer", False))
            override_val = field_obj.get("officer_override_value")
        else:
            fid = getattr(field_obj, "id", None)
            bbox = getattr(field_obj, "bounding_box", None)
            field_verdict = getattr(field_obj, "verdict", "pass")
            confidence = float(getattr(field_obj, "confidence", 1.0))
            reviewed = bool(getattr(field_obj, "reviewed_by_officer", False))
            override_val = getattr(field_obj, "officer_override_value", None)

        threshold = get_field_confidence_threshold(field_name)

        # 1. Officer reviewed path (REV-02)
        if reviewed:
            if field_verdict == "not_applicable":
                return RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    verdict="pass",
                    field_id=fid,
                    field_type=field_name,
                    description=f"Declaration '{field_name}' marked not applicable by officer.",
                    citation=rule.citation,
                    severity=rule.severity,
                    bounding_box=bbox,
                    is_calibrated=True,
                    warning=None,
                )
            elif field_verdict == "fail":
                return RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    verdict="fail",
                    field_id=fid,
                    field_type=field_name,
                    description=f"Mandatory declaration '{field_name}' marked non-compliant by officer.",
                    citation=rule.citation,
                    severity=rule.severity,
                    bounding_box=bbox,
                    is_calibrated=True,
                    warning=None,
                )
            else:
                desc = (
                    f"Mandatory declaration '{field_name}' verified by officer (overridden value: '{override_val}')."
                    if override_val
                    else f"Mandatory declaration '{field_name}' confirmed by officer."
                )
                return RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    verdict="pass",
                    field_id=fid,
                    field_type=field_name,
                    description=desc,
                    citation=rule.citation,
                    severity=rule.severity,
                    bounding_box=bbox,
                    is_calibrated=True,
                    warning=None,
                )

        # 2. Unreviewed automated evaluation: check verdict and confidence threshold (REV-01)
        if field_verdict == "needs_review" or confidence < threshold:
            reason = (
                f"confidence {confidence:.0%} below required {threshold:.0%}"
                if confidence < threshold
                else "format ambiguity requiring officer review"
            )
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                verdict="needs_review",
                field_id=fid,
                field_type=field_name,
                description=f"Mandatory declaration '{field_name}' detected ({reason}); officer review required.",
                citation=rule.citation,
                severity=rule.severity,
                bounding_box=bbox,
                is_calibrated=True,
                warning=None,
            )

        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            verdict="pass",
            field_id=fid,
            field_type=field_name,
            description=f"Mandatory declaration '{field_name}' is present and verified.",
            citation=rule.citation,
            severity=rule.severity,
            bounding_box=bbox,
            is_calibrated=True,
            warning=None,
        )

    def _evaluate_font_height(
        self,
        rule: RuleDefinition,
        field_map: dict[str, Any],
        calib_scale: float | None,
        pdp_width_px: float,
        pdp_height_px: float,
    ) -> RuleEvaluationResult:
        field_name = rule.field or "net_quantity"
        field_obj = field_map.get(field_name)

        if not field_obj:
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                verdict="needs_review",
                field_id=None,
                field_type=field_name,
                description=f"Cannot evaluate font height: declaration '{field_name}' is missing.",
                citation=rule.citation,
                severity=rule.severity,
                bounding_box=None,
                is_calibrated=calib_scale is not None,
                warning="Missing target declaration for font height measurement.",
            )

        if isinstance(field_obj, dict):
            fid = field_obj.get("id")
            bbox = field_obj.get("bounding_box") or {}
            h_px = float(bbox.get("h", 0.0) if isinstance(bbox, dict) else 0.0)
            reviewed = bool(field_obj.get("reviewed_by_officer", False))
            field_verdict = field_obj.get("verdict", "pass")
        else:
            fid = getattr(field_obj, "id", None)
            bbox = getattr(field_obj, "bounding_box", None) or {}
            h_px = float(bbox.get("h", 0.0) if isinstance(bbox, dict) else 0.0)
            reviewed = bool(getattr(field_obj, "reviewed_by_officer", False))
            field_verdict = getattr(field_obj, "verdict", "pass")

        if reviewed and field_verdict == "not_applicable":
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                verdict="pass",
                field_id=fid,
                field_type=field_name,
                description=f"Font height check for '{field_name}' marked not applicable by officer.",
                citation=rule.citation,
                severity=rule.severity,
                bounding_box=bbox,
                is_calibrated=calib_scale is not None,
                warning=None,
            )

        # Uncalibrated Fallback Path (CAL-03 + Rule 7)
        if calib_scale is None or calib_scale <= 0:
            pdp_ratio = round(h_px / pdp_height_px, 4) if pdp_height_px > 0 else 0.0
            if reviewed:
                return RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    verdict="pass",
                    field_id=fid,
                    field_type=field_name,
                    description=f"Font height evaluated via uncalibrated PDP ratio ({pdp_ratio * 100:.2f}% of PDP height). Confirmed by officer.",
                    citation=rule.citation,
                    severity=rule.severity,
                    bounding_box=bbox,
                    is_calibrated=False,
                    warning=None,
                )

            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                verdict="needs_review",
                field_id=fid,
                field_type=field_name,
                description=f"Font height evaluated via uncalibrated PDP ratio ({pdp_ratio * 100:.2f}% of PDP height). Optical calibration reference missing.",
                citation=rule.citation,
                severity=rule.severity,
                bounding_box=bbox,
                is_calibrated=False,
                warning="Uncalibrated measurement: physical millimeter font height cannot be asserted without barcode optical reference (CAL-03). Officer check advised.",
            )

        # Calibrated Path: Calculate PDP area in cm²
        pdp_area_cm2 = (pdp_width_px * calib_scale * pdp_height_px * calib_scale) / 100.0
        threshold_mm = self._determine_target_font_threshold(pdp_area_cm2, rule.thresholds_mm or {})
        measured_height_mm = round(h_px * calib_scale, 2)

        if measured_height_mm >= threshold_mm:
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                verdict="pass",
                field_id=fid,
                field_type=field_name,
                description=f"Font height of {measured_height_mm:.2f}mm meets the required {threshold_mm:.1f}mm for PDP area {pdp_area_cm2:.1f}cm².",
                citation=rule.citation,
                severity=rule.severity,
                bounding_box=bbox,
                is_calibrated=True,
                warning=None,
            )

        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            verdict="fail",
            field_id=fid,
            field_type=field_name,
            description=f"Font height of {measured_height_mm:.2f}mm is below the required minimum {threshold_mm:.1f}mm for PDP area {pdp_area_cm2:.1f}cm².",
            citation=rule.citation,
            severity=rule.severity,
            bounding_box=bbox,
            is_calibrated=True,
            warning=None,
        )

    def _evaluate_legibility_contrast(
        self,
        rule: RuleDefinition,
        field_map: dict[str, Any],
    ) -> RuleEvaluationResult:
        """
        Evaluates legibility and prominence per Rule 9 of LM(PC) Rules, 2011.
        Declarations must not be obscured, blurred, or having low confidence (<0.70).
        """
        field_name = rule.field or "mrp"
        field_obj = field_map.get(field_name)

        if not field_obj:
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                verdict="needs_review",
                field_id=None,
                field_type=field_name,
                description=f"Cannot evaluate legibility: declaration '{field_name}' is missing.",
                citation=rule.citation,
                severity=rule.severity,
                bounding_box=None,
                is_calibrated=True,
                warning="Missing declaration for legibility check.",
            )

        if isinstance(field_obj, dict):
            fid = field_obj.get("id")
            bbox = field_obj.get("bounding_box")
            confidence = float(field_obj.get("confidence", 1.0))
            reviewed = bool(field_obj.get("reviewed_by_officer", False))
        else:
            fid = getattr(field_obj, "id", None)
            bbox = getattr(field_obj, "bounding_box", None)
            confidence = float(getattr(field_obj, "confidence", 1.0))
            reviewed = bool(getattr(field_obj, "reviewed_by_officer", False))

        if reviewed:
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                verdict="pass",
                field_id=fid,
                field_type=field_name,
                description=f"Declaration '{field_name}' legibility and contrast confirmed by officer.",
                citation=rule.citation,
                severity=rule.severity,
                bounding_box=bbox,
                is_calibrated=True,
                warning=None,
            )

        if confidence < 0.70:
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                verdict="needs_review",
                field_id=fid,
                field_type=field_name,
                description=f"Declaration '{field_name}' shows poor contrast or OCR ambiguity (confidence {confidence:.0%}).",
                citation=rule.citation,
                severity=rule.severity,
                bounding_box=bbox,
                is_calibrated=True,
                warning="Low legibility contrast detected; visual verification recommended per Rule 9.",
            )

        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            verdict="pass",
            field_id=fid,
            field_type=field_name,
            description=f"Declaration '{field_name}' satisfies statutory legibility and prominence requirements.",
            citation=rule.citation,
            severity=rule.severity,
            bounding_box=bbox,
            is_calibrated=True,
            warning=None,
        )
