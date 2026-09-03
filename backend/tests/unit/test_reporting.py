import json
import uuid
from datetime import datetime, timezone

from app.services.reporting.disclaimer import (
    MANDATORY_LEGAL_DISCLAIMER_HTML,
    MANDATORY_LEGAL_DISCLAIMER_TEXT,
    MANDATORY_LEGAL_DISCLAIMER_TITLE,
)
from app.services.reporting.service import ReportService


def test_mandatory_legal_disclaimer_constants():
    """Verify RPT-02: Disclaimer text is explicit, comprehensive, and non-empty."""
    assert len(MANDATORY_LEGAL_DISCLAIMER_TEXT) > 100
    assert "Legal Metrology" in MANDATORY_LEGAL_DISCLAIMER_TEXT
    assert "decision-support" in MANDATORY_LEGAL_DISCLAIMER_TEXT.lower()
    assert "NOT constitute a judicial ruling" in MANDATORY_LEGAL_DISCLAIMER_TEXT or "not constitute a judicial ruling" in MANDATORY_LEGAL_DISCLAIMER_TEXT.lower()
    assert MANDATORY_LEGAL_DISCLAIMER_TITLE in MANDATORY_LEGAL_DISCLAIMER_HTML


def test_html_template_renders_mandatory_disclaimer():
    """Verify RPT-01 and RPT-02: Rendered HTML includes un-omittable disclaimer."""
    service = ReportService()

    context = {
        "inspection": {
            "id": str(uuid.uuid4()),
            "commodity_category": "packaged_food",
            "rule_pack_version": "2026.02.01",
            "status": "completed",
        },
        "officer": {
            "full_name": "S. Verma",
            "email": "verma@gov.in",
            "region": "Delhi",
        },
        "fields": [
            {
                "field_type": "net_quantity",
                "raw_text": "500g",
                "parsed_value": "500g",
                "confidence": 0.95,
                "bounding_box": {"h": 40},
                "verdict": "pass",
                "reviewed_by_officer": True,
                "source_image_id": "img-01",
            }
        ],
        "images": [{"id": "img-01", "calibration_scale_mm_per_px": 0.09}],
        "violations": [],
        "audit_logs": [],
    }

    html = service.render_html(context)

    # Disclaimer check (RPT-02)
    assert "STATUTORY NOTICE" in html
    assert "LEGAL DISCLAIMER" in html
    assert "decision-support" in html.lower()
    assert "Legal Metrology (Packaged Commodities) Rules, 2011" in html

    # Findings check (RPT-01)
    assert "Net Quantity" in html
    assert "500g" in html
    assert "Government of India" in html


def test_pdf_generation_produces_valid_document():
    """Verify RPT-01: PDF output starts with %PDF- and contains substantial byte payload."""
    service = ReportService()

    context = {
        "inspection": {
            "id": str(uuid.uuid4()),
            "commodity_category": "edible_oil",
            "rule_pack_version": "2026.02.01",
            "status": "completed",
        },
        "officer": {
            "full_name": "R. Sharma",
            "email": "sharma@gov.in",
            "region": "Mumbai",
        },
        "fields": [
            {
                "field_type": "mrp",
                "raw_text": "MRP Rs 220",
                "parsed_value": "220",
                "confidence": 0.88,
                "bounding_box": {"h": 35},
                "verdict": "pass",
                "reviewed_by_officer": False,
            }
        ],
        "images": [],
        "violations": [
            {
                "rule_id": "mrp-declaration",
                "description": "Missing tax inclusive qualifier",
                "citation": "Rule 6(1)(e)",
                "severity": "minor",
            }
        ],
        "audit_logs": [
            {
                "action": "field_confirm",
                "entity_type": "extracted_field",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }

    pdf_bytes, engine = service.generate_pdf(context)
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")
    assert engine in ("weasyprint", "fpdf2")


def test_editable_export_contains_full_dataset_and_disclaimer():
    """Verify RPT-04 and RPT-02: Editable JSON export includes full schema + statutory notice."""
    service = ReportService()

    insp_id = str(uuid.uuid4())
    context = {
        "inspection": {
            "id": insp_id,
            "commodity_category": "spices",
            "rule_pack_version": "2026.02.01",
            "status": "completed",
        },
        "officer": {
            "full_name": "A. Patel",
            "email": "patel@gov.in",
            "region": "Gujarat",
        },
        "fields": [
            {
                "field_type": "mfg_date",
                "raw_text": "01/2026",
                "parsed_value": "2026-01",
                "confidence": 0.94,
                "bounding_box": {"x": 10, "y": 20, "w": 100, "h": 25},
                "verdict": "pass",
                "reviewed_by_officer": False,
            }
        ],
        "images": [],
        "violations": [],
        "audit_logs": [],
    }

    json_bytes = service.generate_editable_export(context)
    data = json.loads(json_bytes.decode("utf-8"))

    assert data["format"] == "editable"
    assert data["inspection"]["id"] == insp_id
    assert len(data["declarations"]) == 1
    assert data["declarations"][0]["field_type"] == "mfg_date"

    # Mandatory Legal Disclaimer Check (RPT-02)
    assert "legal_disclaimer" in data
    assert data["legal_disclaimer"]["title"] == MANDATORY_LEGAL_DISCLAIMER_TITLE
    assert data["legal_disclaimer"]["text"] == MANDATORY_LEGAL_DISCLAIMER_TEXT
