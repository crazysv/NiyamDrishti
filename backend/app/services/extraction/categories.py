from typing import Any

from pydantic import BaseModel


class CommodityCategory(BaseModel):
    id: str
    name: str
    description: str
    specific_rule_flags: list[str] = []


COMMODITY_CATEGORIES: list[CommodityCategory] = [
    CommodityCategory(
        id="general",
        name="General Pre-Packaged Commodity",
        description="Standard consumer packaged goods governed by Legal Metrology (Packaged Commodities) Rules, 2011.",
        specific_rule_flags=["standard_declarations"],
    ),
    CommodityCategory(
        id="food",
        name="Food & Beverages",
        description="Packaged foodstuffs requiring net weight declarations, best before/expiry, and nutritional panel alignment.",
        specific_rule_flags=["standard_declarations", "food_net_weight_tolerance"],
    ),
    CommodityCategory(
        id="cosmetics",
        name="Cosmetics & Personal Care",
        description="Personal care, soap, shampoo, lotions, and cosmetics packages.",
        specific_rule_flags=["standard_declarations", "cosmetics_batch_rules"],
    ),
    CommodityCategory(
        id="pan_masala",
        name="Pan Masala & Tobacco Products",
        description="Pan masala and related items subject to strict Retail Sale Price (RSP) declarations and size constraints.",
        specific_rule_flags=["pan_masala_rsp_rule", "health_warning_ratio"],
    ),
    CommodityCategory(
        id="electronics",
        name="Electronics & Appliances",
        description="Consumer electrical and electronic goods requiring rated voltage, energy stars, and importer details.",
        specific_rule_flags=["standard_declarations", "e_waste_declaration"],
    ),
    CommodityCategory(
        id="medical_device",
        name="Medical Devices",
        description="Medical devices subject to Medical Device Rules, 2017 font and sterile packaging specifications.",
        specific_rule_flags=["medical_device_2017_rules"],
    ),
    CommodityCategory(
        id="garments",
        name="Apparel, Textiles & Footwear",
        description="Garments and textiles declaring fiber composition, piece dimensions (meters/cm), and international size codes.",
        specific_rule_flags=["textile_fiber_composition", "dimension_metric_units"],
    ),
]


def get_category_by_id(category_id: str) -> CommodityCategory | None:
    for cat in COMMODITY_CATEGORIES:
        if cat.id == category_id:
            return cat
    return None


def list_categories() -> list[dict[str, Any]]:
    return [c.model_dump() for c in COMMODITY_CATEGORIES]
