"""
Shared, un-omittable legal disclaimer module (RPT-02).
This disclaimer is a hard product requirement per MASTER_CONTENT.md §10.9/§14.2
and 01_PRD.md US-07. It must be included in every generated report without exception.
"""

MANDATORY_LEGAL_DISCLAIMER_TITLE: str = "STATUTORY NOTICE & LEGAL DISCLAIMER"

MANDATORY_LEGAL_DISCLAIMER_TEXT: str = (
    "This report is an automated, AI-assisted compliance decision-support document generated under "
    "the Legal Metrology (Packaged Commodities) Rules, 2011 and the Legal Metrology Act, 2009. "
    "This document does NOT constitute a judicial ruling, final legal determination, compounding order, "
    "or formal penalty notice. All automated findings, optical character extractions, and dimensional "
    "measurements must be reviewed and verified by an authorized Legal Metrology Officer. "
    "The designated enforcement official bears sole statutory authority for inspection determinations, "
    "evidentiary verification, and compounding proceedings under applicable law."
)

MANDATORY_LEGAL_DISCLAIMER_HTML: str = f"""<div class="legal-disclaimer-box" style="border: 2px solid #333e50; background-color: #f3f3f6; padding: 12px 16px; margin-top: 24px; border-radius: 4px; page-break-inside: avoid;">
  <div style="font-weight: bold; font-size: 11px; text-transform: uppercase; color: #1a1c1e; letter-spacing: 0.05em; margin-bottom: 6px;">
    {MANDATORY_LEGAL_DISCLAIMER_TITLE}
  </div>
  <p style="font-size: 10px; line-height: 1.5; color: #44474c; margin: 0; text-align: justify;">
    {MANDATORY_LEGAL_DISCLAIMER_TEXT}
  </p>
</div>"""
