import logging
import re
import uuid
from collections import defaultdict
from typing import Any

from app.models.base import ExtractedField, InspectionImage, Violation
from app.services.cross_matching.schemas import (
    CrossMatchDiscrepancy,
    CrossMatchReport,
    FieldOccurrence,
)

logger = logging.getLogger(__name__)


class MultiImageCrossMatchingService:
    """
    Performs cross-image declaration consistency validation (E2-03).
    Cross-checks front PDP, back panel, and sticker images for statutory conflicts:
    - Altered MRP stickers exceeding base price (Rule 18(2) & Section 36)
    - Conflicting Net Quantity declarations across panels (Rule 6(1)(c))
    - Inconsistent Mfg Dates or Country of Origin across labels
    """

    def analyze_cross_image_consistency(
        self,
        inspection_id: uuid.UUID,
        images: list[InspectionImage],
        fields: list[ExtractedField],
    ) -> CrossMatchReport:
        image_role_map: dict[uuid.UUID, str] = {img.id: img.image_role for img in images}

        # Group extracted fields by field_type
        fields_by_type: dict[str, list[FieldOccurrence]] = defaultdict(list)

        for f in fields:
            source_id = f.source_image_id
            role = image_role_map.get(source_id, "unknown")

            parsed = f.parsed_value
            occurrences = fields_by_type[f.field_type]
            occurrences.append(
                FieldOccurrence(
                    field_id=f.id,
                    source_image_id=source_id,
                    image_role=role,
                    raw_text=f.raw_text,
                    parsed_value=parsed,
                    confidence=f.confidence,
                    bounding_box=f.bounding_box,
                )
            )

        discrepancies: list[CrossMatchDiscrepancy] = []
        consistent_fields: list[str] = []
        total_compared = 0

        for field_type, occurrences in fields_by_type.items():
            # Cross-matching requires declarations found in at least 2 distinct images
            distinct_images = {occ.source_image_id for occ in occurrences}
            if len(distinct_images) < 2:
                continue

            total_compared += 1
            type_discrepancies: list[CrossMatchDiscrepancy] = []

            if field_type == "mrp":
                type_discrepancies = self._check_mrp_consistency(occurrences)
            elif field_type == "net_quantity":
                type_discrepancies = self._check_net_quantity_consistency(occurrences)
            elif field_type in ("mfg_date", "expiry_date"):
                type_discrepancies = self._check_date_consistency(field_type, occurrences)
            elif field_type == "country_of_origin":
                type_discrepancies = self._check_country_consistency(occurrences)

            if type_discrepancies:
                discrepancies.extend(type_discrepancies)
            else:
                consistent_fields.append(field_type)

        is_consistent = len(discrepancies) == 0

        return CrossMatchReport(
            inspection_id=inspection_id,
            total_images=len(images),
            total_declarations_compared=total_compared,
            is_consistent=is_consistent,
            discrepancies=discrepancies,
            consistent_fields=consistent_fields,
        )

    def _extract_numeric_price(self, val: Any) -> float | None:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            # Extract digits and optional decimals
            match = re.search(r"([0-9]+(?:\.[0-9]{1,2})?)", val)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return None
        return None

    def _check_mrp_consistency(self, occurrences: list[FieldOccurrence]) -> list[CrossMatchDiscrepancy]:
        discrepancies: list[CrossMatchDiscrepancy] = []

        sticker_occs = [occ for occ in occurrences if occ.image_role == "sticker"]
        base_occs = [occ for occ in occurrences if occ.image_role != "sticker"]

        # 1. Sticker vs Base Package MRP (Anti-Smudging / Rule 18(2))
        if sticker_occs and base_occs:
            for s_occ in sticker_occs:
                s_price = self._extract_numeric_price(s_occ.parsed_value)
                for b_occ in base_occs:
                    b_price = self._extract_numeric_price(b_occ.parsed_value)
                    if s_price is not None and b_price is not None:
                        # If sticker price is higher than base price, illegal alteration
                        if s_price > b_price:
                            discrepancies.append(
                                CrossMatchDiscrepancy(
                                    field_type="mrp",
                                    discrepancy_type="mrp_altered_sticker",
                                    severity="critical",
                                    rule_id="cross-match-mrp-sticker-increase",
                                    citation="LM(PC) Rules 2011, Rule 18(2) & Legal Metrology Act Section 36",
                                    description=(
                                        f"Altered MRP sticker detected: sticker price (Rs. {s_price:.2f}) exceeds "
                                        f"original base package price (Rs. {b_price:.2f})."
                                    ),
                                    source_image_ids=[s_occ.source_image_id, b_occ.source_image_id],
                                    occurrences=[s_occ, b_occ],
                                )
                            )
                        elif s_price != b_price:
                            # If sticker price is lower (discount sticker), note as minor discrepancy/review
                            discrepancies.append(
                                CrossMatchDiscrepancy(
                                    field_type="mrp",
                                    discrepancy_type="mrp_sticker_mismatch",
                                    severity="minor",
                                    rule_id="cross-match-mrp-sticker-discount",
                                    citation="LM(PC) Rules 2011, Rule 6 & Rule 18",
                                    description=(
                                        f"Promotional/discount sticker detected: sticker price Rs. {s_price:.2f} "
                                        f"differs from base price Rs. {b_price:.2f}."
                                    ),
                                    source_image_ids=[s_occ.source_image_id, b_occ.source_image_id],
                                    occurrences=[s_occ, b_occ],
                                )
                            )

        # 2. Conflicting MRP declarations on base package panels
        if len(base_occs) >= 2:
            prices = [(occ, self._extract_numeric_price(occ.parsed_value)) for occ in base_occs]
            valid_prices = [(occ, p) for occ, p in prices if p is not None]
            if len(valid_prices) >= 2:
                first_occ, first_price = valid_prices[0]
                for next_occ, next_price in valid_prices[1:]:
                    if abs(first_price - next_price) > 0.01:
                        discrepancies.append(
                            CrossMatchDiscrepancy(
                                field_type="mrp",
                                discrepancy_type="mrp_panel_conflict",
                                severity="critical",
                                rule_id="cross-match-mrp-panel-conflict",
                                citation="LM(PC) Rules 2011, Rule 6(1)",
                                description=(
                                    f"Conflicting MRP values on package: {first_occ.image_role} declares Rs. {first_price:.2f}, "
                                    f"while {next_occ.image_role} declares Rs. {next_price:.2f}."
                                ),
                                source_image_ids=[first_occ.source_image_id, next_occ.source_image_id],
                                occurrences=[first_occ, next_occ],
                            )
                        )

        return discrepancies

    def _check_net_quantity_consistency(self, occurrences: list[FieldOccurrence]) -> list[CrossMatchDiscrepancy]:
        discrepancies: list[CrossMatchDiscrepancy] = []
        if len(occurrences) < 2:
            return discrepancies

        def norm_qty(val: Any) -> str:
            s = str(val).strip().lower()
            return re.sub(r"\s+", " ", s)

        first = occurrences[0]
        first_norm = norm_qty(first.parsed_value)

        for other in occurrences[1:]:
            other_norm = norm_qty(other.parsed_value)
            if first_norm and other_norm and first_norm != other_norm:
                discrepancies.append(
                    CrossMatchDiscrepancy(
                        field_type="net_quantity",
                        discrepancy_type="net_quantity_mismatch",
                        severity="major",
                        rule_id="cross-match-net-quantity-mismatch",
                        citation="LM(PC) Rules 2011, Rule 6(1)(c) & Rule 12",
                        description=(
                            f"Net quantity mismatch across package panels: '{first.parsed_value}' on {first.image_role} "
                            f"vs '{other.parsed_value}' on {other.image_role}."
                        ),
                        source_image_ids=[first.source_image_id, other.source_image_id],
                        occurrences=[first, other],
                    )
                )

        return discrepancies

    def _check_date_consistency(
        self, field_type: str, occurrences: list[FieldOccurrence]
    ) -> list[CrossMatchDiscrepancy]:
        discrepancies: list[CrossMatchDiscrepancy] = []
        if len(occurrences) < 2:
            return discrepancies

        first = occurrences[0]
        first_val = str(first.parsed_value).strip().lower()

        for other in occurrences[1:]:
            other_val = str(other.parsed_value).strip().lower()
            if first_val and other_val and first_val != other_val:
                discrepancies.append(
                    CrossMatchDiscrepancy(
                        field_type=field_type,
                        discrepancy_type="date_mismatch",
                        severity="major",
                        rule_id=f"cross-match-{field_type}-mismatch",
                        citation="LM(PC) Rules 2011, Rule 6(1)(d)",
                        description=(
                            f"{field_type.replace('_', ' ').title()} mismatch: '{first.parsed_value}' on {first.image_role} "
                            f"differs from '{other.parsed_value}' on {other.image_role}."
                        ),
                        source_image_ids=[first.source_image_id, other.source_image_id],
                        occurrences=[first, other],
                    )
                )

        return discrepancies

    def _check_country_consistency(self, occurrences: list[FieldOccurrence]) -> list[CrossMatchDiscrepancy]:
        discrepancies: list[CrossMatchDiscrepancy] = []
        if len(occurrences) < 2:
            return discrepancies

        first = occurrences[0]
        first_val = str(first.parsed_value).strip().lower()

        for other in occurrences[1:]:
            other_val = str(other.parsed_value).strip().lower()
            if first_val and other_val and first_val != other_val:
                discrepancies.append(
                    CrossMatchDiscrepancy(
                        field_type="country_of_origin",
                        discrepancy_type="country_mismatch",
                        severity="major",
                        rule_id="cross-match-country-mismatch",
                        citation="LM(PC) Rules 2011, Rule 6(1)(e)",
                        description=(
                            f"Conflicting country of origin declarations: '{first.parsed_value}' on {first.image_role} "
                            f"vs '{other.parsed_value}' on {other.image_role}."
                        ),
                        source_image_ids=[first.source_image_id, other.source_image_id],
                        occurrences=[first, other],
                    )
                )

        return discrepancies

    def to_violations(
        self,
        inspection_id: uuid.UUID,
        rule_pack_version: str,
        discrepancies: list[CrossMatchDiscrepancy],
    ) -> list[Violation]:
        """Converts detected cross-matching discrepancies into persistent database Violation records."""
        violations: list[Violation] = []
        for disc in discrepancies:
            # Associate with the first occurrence field if available
            primary_fid = disc.occurrences[0].field_id if disc.occurrences else None
            violations.append(
                Violation(
                    id=uuid.uuid4(),
                    inspection_id=inspection_id,
                    extracted_field_id=primary_fid,
                    rule_id=disc.rule_id,
                    rule_pack_version=rule_pack_version,
                    description=disc.description,
                    citation=disc.citation,
                    severity=disc.severity,
                )
            )
        return violations
