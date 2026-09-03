import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services.reporting.disclaimer import (
    MANDATORY_LEGAL_DISCLAIMER_TEXT,
    MANDATORY_LEGAL_DISCLAIMER_TITLE,
)

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


class ReportService:
    """
    Inspection Compliance Report Generator supporting:
    - RPT-01: HTML to PDF generation via WeasyPrint with evidence and metadata.
    - RPT-02: Mandatory, un-omittable statutory disclaimer partial on all report variants.
    - RPT-03: Cloudflare R2 and local filesystem storage.
    - RPT-04: Editable format export (JSON/structured data).
    - Seamless fallback to FPDF2 when host system lacks WeasyPrint native libraries.
    """

    def __init__(self):
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_html(self, context: dict[str, Any]) -> str:
        """Renders the HTML inspection report template."""
        # Ensure mandatory disclaimer variables are always present (RPT-02)
        context["disclaimer_title"] = MANDATORY_LEGAL_DISCLAIMER_TITLE
        context["disclaimer_text"] = MANDATORY_LEGAL_DISCLAIMER_TEXT
        if "generated_at_str" not in context:
            context["generated_at_str"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        template = self.jinja_env.get_template("reports/inspection_report.html")
        return template.render(context)

    def generate_pdf(self, context: dict[str, Any]) -> tuple[bytes, str]:
        """
        Generates PDF report bytes.
        Attempts WeasyPrint first; if native dependencies are missing,
        transparently uses FPDF2 engine without failing.
        Returns: (pdf_bytes, engine_used)
        """
        # Render Jinja2 HTML with mandatory disclaimer
        rendered_html = self.render_html(context)

        # 1. Attempt WeasyPrint (Primary)
        try:
            import weasyprint

            pdf_bytes = weasyprint.HTML(string=rendered_html).write_pdf()
            logger.info("Report successfully generated via WeasyPrint engine.")
            return pdf_bytes, "weasyprint"
        except (ImportError, OSError) as exc:
            logger.warning(f"WeasyPrint unavailable on this host ({exc}). Falling back to FPDF2 engine (Tech Spec §2).")

        # 2. FPDF2 Fallback Engine
        pdf_bytes = self._generate_fpdf_report(context)
        return pdf_bytes, "fpdf2"

    def _generate_fpdf_report(self, context: dict[str, Any]) -> bytes:
        """
        Generates an official A4 compliance report using FPDF2.
        Includes all declaration findings, violations, audit logs, and mandatory disclaimer.
        """
        from fpdf import FPDF

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        inspection = context.get("inspection", {})
        officer = context.get("officer", {})
        fields = context.get("fields", [])
        violations = context.get("violations", [])
        audit_logs = context.get("audit_logs", [])
        generated_at_str = context.get("generated_at_str", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

        def _clean_latin1(val: Any) -> str:
            if val is None:
                return ""
            s = str(val)
            replacements = {
                "—": "-",
                "–": "-",
                "“": '"',
                "”": '"',
                "‘": "'",
                "’": "'",
                "₹": "Rs.",
                "•": "*",
                "…": "...",
                "≥": ">=",
                "≤": "<=",
                "±": "+/-",
                "°": " deg",
            }
            for orig, rep in replacements.items():
                s = s.replace(orig, rep)
            return s.encode("latin-1", errors="replace").decode("latin-1")

        # Header: Government of India
        pdf.set_font("helvetica", "B", 14)
        pdf.set_text_color(17, 28, 44)
        pdf.cell(0, 7, "GOVERNMENT OF INDIA", new_x="LMARGIN", new_y="NEXT", align="C")

        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(86, 97, 85)
        pdf.cell(
            0, 5, "DEPARTMENT OF CONSUMER AFFAIRS - LEGAL METROLOGY DIVISION", new_x="LMARGIN", new_y="NEXT", align="C"
        )

        pdf.set_font("helvetica", "B", 11)
        pdf.set_text_color(51, 62, 80)
        pdf.cell(
            0, 6, "LEGAL METROLOGY (PACKAGED COMMODITIES) COMPLIANCE REPORT", new_x="LMARGIN", new_y="NEXT", align="C"
        )
        pdf.ln(3)

        # Divider line
        pdf.set_draw_color(51, 62, 80)
        pdf.set_line_width(0.6)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(4)

        # Overall Status Banner
        is_compliant = len(violations) == 0
        if is_compliant:
            pdf.set_fill_color(214, 227, 211)  # Emerald light
            pdf.set_text_color(19, 30, 20)
            status_text = "COMPLIANT - ALL MANDATORY DECLARATIONS VERIFIED"
        else:
            pdf.set_fill_color(255, 218, 214)  # Red light
            pdf.set_text_color(147, 0, 10)
            status_text = f"NON-COMPLIANT - {len(violations)} STATUTORY DEFICIENCY/VIOLATION DETECTED"

        pdf.set_font("helvetica", "B", 9)
        pdf.cell(0, 8, _clean_latin1(status_text), border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # Inspection Metadata Block
        pdf.set_fill_color(243, 243, 246)
        pdf.set_draw_color(226, 226, 229)
        pdf.set_text_color(26, 28, 30)
        pdf.set_font("helvetica", "", 8)

        insp_id_str = str(getattr(inspection, "id", None) or inspection.get("id", ""))
        category = str(
            getattr(inspection, "commodity_category", None) or inspection.get("commodity_category", "general")
        )
        pack_version = str(
            getattr(inspection, "rule_pack_version", None) or inspection.get("rule_pack_version", "2026.02.01")
        )
        officer_name = str(getattr(officer, "full_name", None) or officer.get("full_name", "Officer"))
        region = str(getattr(officer, "region", None) or officer.get("region", "Delhi"))

        meta_lines = [
            f"Inspection ID: {insp_id_str[:18]}...    |    Date: {generated_at_str}    |    Rule Pack: v{pack_version}",
            f"Commodity: {category.replace('_', ' ').title()}    |    Officer: {officer_name}    |    Region: {region}",
        ]
        for line in meta_lines:
            pdf.cell(0, 5, _clean_latin1(line), border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Section 1: Findings Table
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(51, 62, 80)
        pdf.cell(0, 6, "1. Mandatory Declaration Compliance Findings", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        # Table Header
        col_w = [45, 60, 25, 25, 25]  # sum = 180mm
        pdf.set_font("helvetica", "B", 8)
        pdf.set_fill_color(51, 62, 80)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(col_w[0], 6, "Declaration Field", border=1, fill=True)
        pdf.cell(col_w[1], 6, "Verified / Extracted Value", border=1, fill=True)
        pdf.cell(col_w[2], 6, "Confidence", border=1, fill=True)
        pdf.cell(col_w[3], 6, "Verdict", border=1, fill=True)
        pdf.cell(col_w[4], 6, "Citation", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("helvetica", "", 7.5)
        pdf.set_text_color(26, 28, 30)

        for f in fields:
            ftype = (
                str(getattr(f, "field_type", None) or (f.get("field_type") if isinstance(f, dict) else ""))
                .replace("_", " ")
                .title()
            )
            val = str(
                getattr(f, "officer_override_value", None)
                or getattr(f, "parsed_value", None)
                or getattr(f, "raw_text", None)
                or (
                    f.get("officer_override_value") or f.get("parsed_value") or f.get("raw_text")
                    if isinstance(f, dict)
                    else "-"
                )
            )
            conf_val = float(
                getattr(f, "confidence", 1.0) or (f.get("confidence", 1.0) if isinstance(f, dict) else 1.0)
            )
            verdict = str(
                getattr(f, "verdict", "pass") or (f.get("verdict", "pass") if isinstance(f, dict) else "pass")
            ).upper()
            reviewed = bool(
                getattr(f, "reviewed_by_officer", False)
                or (f.get("reviewed_by_officer", False) if isinstance(f, dict) else False)
            )

            if reviewed:
                ftype += " *"

            pdf.cell(col_w[0], 5, _clean_latin1(ftype[:24]), border=1)
            pdf.cell(col_w[1], 5, _clean_latin1(val[:36]), border=1)
            pdf.cell(col_w[2], 5, f"{int(conf_val * 100)}%", border=1)
            pdf.cell(col_w[3], 5, _clean_latin1(verdict), border=1)
            pdf.cell(col_w[4], 5, "Rule 6/7", border=1, new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)

        # Section 2: Statutory Violations
        if violations:
            pdf.set_font("helvetica", "B", 10)
            pdf.set_text_color(186, 26, 26)
            pdf.cell(0, 6, "2. Detected Statutory Violations & Non-Compliance", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

            for v in violations:
                rule_id = str(getattr(v, "rule_id", None) or (v.get("rule_id") if isinstance(v, dict) else ""))
                desc = str(getattr(v, "description", None) or (v.get("description") if isinstance(v, dict) else ""))
                citation = str(
                    getattr(v, "citation", None) or (v.get("citation") if isinstance(v, dict) else "LM(PC) Rules 2011")
                )
                sev = str(
                    getattr(v, "severity", "major") or (v.get("severity", "major") if isinstance(v, dict) else "major")
                ).upper()

                pdf.set_fill_color(255, 248, 247)
                pdf.set_draw_color(255, 218, 214)
                pdf.set_font("helvetica", "B", 8)
                pdf.set_text_color(186, 26, 26)
                pdf.cell(
                    0, 5, _clean_latin1(f"[{sev}] {rule_id}"), border="LTR", fill=True, new_x="LMARGIN", new_y="NEXT"
                )

                pdf.set_font("helvetica", "", 7.5)
                pdf.set_text_color(26, 28, 30)
                pdf.multi_cell(0, 4, _clean_latin1(desc), border="LR", fill=True)

                pdf.set_font("helvetica", "I", 7)
                pdf.set_text_color(86, 97, 85)
                pdf.cell(
                    0,
                    4,
                    _clean_latin1(f"Statutory Citation: {citation}"),
                    border="LBR",
                    fill=True,
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.ln(2)

        # Section 3: Officer Human Review & Decision Audit Trail
        if audit_logs:
            pdf.set_font("helvetica", "B", 9)
            pdf.set_text_color(51, 62, 80)
            pdf.cell(0, 5, "3. Officer Review & Decision Audit Trail", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            pdf.set_font("helvetica", "", 7)
            for log in audit_logs[:5]:
                action = str(getattr(log, "action", None) or (log.get("action") if isinstance(log, dict) else ""))
                entity = str(
                    getattr(log, "entity_type", None) or (log.get("entity_type") if isinstance(log, dict) else "")
                )
                log_time = str(
                    getattr(log, "created_at", None) or (log.get("created_at") if isinstance(log, dict) else "")
                )[:19]
                pdf.cell(
                    0, 4, _clean_latin1(f"[{log_time}] Action: {action} on {entity}"), new_x="LMARGIN", new_y="NEXT"
                )
            pdf.ln(2)

        # Section 4: Officer Attestation & Signature
        pdf.ln(4)
        pdf.set_draw_color(26, 28, 30)
        y_sig = pdf.get_y() + 10
        pdf.line(15, y_sig, 85, y_sig)
        pdf.line(125, y_sig, 195, y_sig)

        pdf.set_xy(15, y_sig + 1)
        pdf.set_font("helvetica", "B", 8)
        pdf.set_text_color(26, 28, 30)
        pdf.cell(70, 4, _clean_latin1(f"Inspecting Officer: {officer_name}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 7)
        pdf.cell(70, 3, _clean_latin1(f"Legal Metrology Officer - {region}"), new_x="LMARGIN", new_y="NEXT")

        pdf.set_xy(125, y_sig + 1)
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(70, 4, "Official Seal / Counter-Signature", new_x="LMARGIN", new_y="NEXT")
        pdf.set_xy(125, y_sig + 5)
        pdf.set_font("helvetica", "", 7)
        pdf.cell(70, 3, f"Date: {generated_at_str}")

        pdf.ln(10)

        # Mandatory Statutory Notice & Legal Disclaimer (RPT-02)
        pdf.set_fill_color(243, 243, 246)
        pdf.set_draw_color(51, 62, 80)
        pdf.set_line_width(0.4)

        pdf.set_font("helvetica", "B", 8)
        pdf.set_text_color(17, 28, 44)
        pdf.cell(
            0,
            5,
            _clean_latin1(MANDATORY_LEGAL_DISCLAIMER_TITLE),
            border="LTR",
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )

        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(68, 71, 76)
        pdf.multi_cell(0, 3.5, _clean_latin1(MANDATORY_LEGAL_DISCLAIMER_TEXT), border="LBR", fill=True)

        return bytes(pdf.output())

    def generate_editable_export(self, context: dict[str, Any]) -> bytes:
        """
        Generates an editable format export (JSON structured format) alongside PDF (RPT-04).
        Always includes the mandatory legal disclaimer (RPT-02).
        """
        inspection = context.get("inspection", {})
        officer = context.get("officer", {})
        fields = context.get("fields", [])
        violations = context.get("violations", [])
        audit_logs = context.get("audit_logs", [])

        def to_dict(obj: Any) -> Any:
            if isinstance(obj, dict):
                return obj
            if hasattr(obj, "__dict__"):
                d = {}
                for k, v in obj.__dict__.items():
                    if not k.startswith("_"):
                        if isinstance(v, (datetime,)):
                            d[k] = v.isoformat()
                        elif hasattr(v, "hex"):
                            d[k] = str(v)
                        else:
                            d[k] = v
                return d
            return str(obj)

        export_data = {
            "format": "editable",
            "report_schema_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "inspection": to_dict(inspection),
            "officer": to_dict(officer),
            "declarations": [to_dict(f) for f in fields],
            "violations": [to_dict(v) for v in violations],
            "audit_trail": [to_dict(a) for a in audit_logs],
            # Mandatory Statutory Disclaimer (RPT-02)
            "legal_disclaimer": {
                "title": MANDATORY_LEGAL_DISCLAIMER_TITLE,
                "text": MANDATORY_LEGAL_DISCLAIMER_TEXT,
                "statutory_basis": "Legal Metrology (Packaged Commodities) Rules, 2011",
            },
        }

        return json.dumps(export_data, indent=2, default=str).encode("utf-8")
