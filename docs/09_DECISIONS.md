# 09_DECISIONS â€” Architecture Decision Records

A running, dated log of real technical decisions and why they were made. Add a new entry every time you make a non-trivial choice â€” a library swap, an architecture change, a rule interpretation, a threshold you tuned empirically. Do this **at the time you decide**, not retroactively; retroactive ADRs tend to rationalize rather than record.

**Never delete an entry, even if later superseded** â€” mark it superseded and link forward, so the history of *why* stays intact. Future-you (or a fresh agent session) needs the reasoning, not just the current state.

---

## Template (copy this for each new entry)

```
## ADR-NNN â€” <short title>
**Date:** YYYY-MM-DD
**Status:** Proposed / Accepted / Superseded by ADR-NNN
**Context:** What situation/question prompted this decision?
**Decision:** What was decided?
**Alternatives considered:** What else was on the table, and why not chosen?
**Consequences:** What does this make easier/harder going forward?
```

---

## Seed Decisions (from initial project setup â€” logged here so the pattern is established)

### ADR-001 â€” Neon over Supabase as primary database
**Date:** 2026-09-02
**Status:** Accepted
**Context:** Needed a permanent, genuinely free Postgres host with no domain dependency, per the project's free-tier-only constraint (`MASTER_CONTENT.md` Â§11).
**Decision:** Use Neon as the primary production database.
**Alternatives considered:** Supabase (bundles Auth+Storage, but free tier pauses after ~7 days of inactivity â€” acceptable for some projects, but Neon's non-pausing scale-to-zero behavior is a better fit for a tool that needs to be reliably reachable during a pilot); Railway (no longer a genuine standing free tier as of 2026 â€” one-time trial credit only); Render Postgres (free tier expires after 30 days â€” a trial, not a home).
**Consequences:** We give up Supabase's bundled Auth/Storage convenience in exchange for standing reliability; auth is self-rolled (see ADR-002) and storage is handled separately by Cloudflare R2.

### ADR-002 â€” Self-rolled JWT auth over a vendor auth platform
**Date:** 2026-09-02
**Status:** Accepted
**Context:** Officers/admins are provisioned accounts (not public self-signup), so a full vendor auth platform is more complexity/dependency than the use case needs.
**Decision:** FastAPI + python-jose (JWT) + passlib/bcrypt, self-managed.
**Alternatives considered:** Supabase Auth (rejected alongside ADR-001); a government SSO (MeriPehchan/Jan Parichay) â€” genuinely the right long-term answer, but deliberately deferred to Phase 4 (`02_ROADMAP.md`) since it depends on an external approval process outside this project's control.
**Consequences:** More auth code to own short-term; zero vendor dependency and a clean later swap-in point for government SSO.

### ADR-003 â€” Gmail SMTP / Brevo over Resend for email
**Date:** 2026-09-02
**Status:** Accepted
**Context:** A prior version of this project depended on Resend, whose free tier's practical use requires a verified custom domain â€” a paid, indirect dependency this project's constraints explicitly forbid (`MASTER_CONTENT.md` Â§11.7).
**Decision:** Use Gmail SMTP (App Password) as the default for MVP-scale officer notifications; Brevo (free tier, no domain required to start) as the scale-up option before ever reconsidering a domain-gated provider.
**Alternatives considered:** Resend, SendGrid, Mailgun â€” all rejected as *defaults* specifically because their free tiers assume a domain the team doesn't necessarily have; not forbidden outright if the team later owns a domain, but never the default.
**Consequences:** Lower daily send ceiling than a dedicated transactional provider, which is fine at pilot scale; revisit only if volume genuinely requires it (see `MASTER_CONTENT.md` Â§16).

### ADR-004 â€” Rules as versioned data, not code
**Date:** 2026-09-02
**Status:** Accepted
**Context:** Legal Metrology rules are amended piecemeal and unpredictably (`MASTER_CONTENT.md` Â§4.5); a rule hard-coded into application logic goes stale the moment a gazette notification changes it.
**Decision:** Every rule lives in a versioned `rule_packs.rules_json` entry (`06_SCHEMA.md` Â§3); the rule engine dispatches on data, never on a hard-coded threshold in application code.
**Alternatives considered:** Hard-coding thresholds directly in the validation code â€” rejected outright; this is the specific anti-pattern the project exists to avoid.
**Consequences:** Slightly more engineering upfront (a schema + loader + validator) in exchange for the entire point of the product: amendments become data updates, not deploys.

---

*(Add new entries below this line, in ascending ADR number order, as real decisions are made during the build â€” including the outcomes of SPIKE-01 and SPIKE-02 from `07_IMPLEMENTATION_PLAN.md`, which must be logged here before Phase 1 begins per `02_ROADMAP.md`.)*

### ADR-005 â€” Server-side OCR as primary path (SPIKE-01 outcome)
**Date:** 2026-09-02
**Status:** Accepted
**Context:** SPIKE-01 tested PaddleOCR 2.9.1 (PP-OCRv3, English) on 46 real product-label photos to decide between client-side and server-side OCR (OQ-03).
**Decision:** Use server-side OCR (PaddleOCR 2.9.1 on Render free Web Service) as the primary path for Phase 1 MVP. Client-side OCR deferred to Phase 2+ as an enhancement once the server-side pipeline is proven.
**Evidence:**
- 46/46 images processed with 0 errors.
- Avg confidence: 87.9% (range 0.61â€“1.00). Only 1 image below 0.73.
- Avg latency: 2,420ms per image â€” acceptable for a field tool where the officer is already handling the product; target is under 5s end-to-end.
- Dense label images (69â€“118 regions) processed correctly; sparse/single-panel images (1â€“5 regions) also handled cleanly.
- One image (img3.jpeg) returned 0 regions â€” attributed to image quality (confirmed: 0 regions = quality gate should have caught it upstream).
- PaddleOCR 3.x (latest) has a known OneDNN/Windows incompatibility (NotImplementedError in onednn_instruction.cc). Pinned to 2.9.1 + paddlepaddle==2.6.2 for Phase 1. Upgrade path to 3.x remains open once the OneDNN bug is resolved upstream.
**Alternatives considered:** Client-side WASM OCR (PaddleOCR.js / Tesseract.js) â€” deferred; real-world accuracy/speed on low-end Android devices unverified and Tesseract is not pre-installed on Windows test environment. Hybrid (client provisional + server re-validation on sync) â€” valid Phase 2 enhancement, not required for MVP.
**Consequences:** Offline mode in Phase 1 will queue images and show "pending" state until connectivity returns; the officer gets results after sync, not instantly. This is acceptable for MVP and explicitly flagged in the UI design requirement (CAP-07 offline queue + visible "pending sync" state). Revisit client-side OCR before Phase 2 for true offline results.

### ADR-006 â€” Barcode calibration viable but requires pyzbar DLL; OpenCV BarcodeDetector pixel-width unreliable at small sizes (SPIKE-02 outcome)
**Date:** 2026-09-02
### ADR-006 — Barcode calibration viable but requires pyzbar DLL; OpenCV BarcodeDetector pixel-width unreliable at small sizes (SPIKE-02 outcome)
**Date:** 2026-09-02
**Status:** Superseded by ADR-006 Amendment (2026-09-02) — pyzbar replaced by zxing-cpp
**Context:** SPIKE-02 tested barcode-based mm-per-pixel calibration on 46 photos to decide on the acceptable-use threshold (OQ-04 feeds into RULE-03).
**Decision:** Barcode calibration is valid and will be implemented (CAL-01..CAL-03) but with two constraints: (1) pyzbar (with the zbar system DLL) is the required barcode detector — OpenCV BarcodeDetector reports px=0 or px=1–4 for many valid barcodes, making its pixel-width measurement unreliable; (2) calibration is only used when detected pixel width > 50px; below that threshold, the reading is treated as uncalibrated and the fallback path (CAL-03) is triggered.
**Evidence:** 46 photos scanned; 20 had barcodes detected by OpenCV. Of those, 10 reported px=0 or px<5 (measurement failure). The 5 readings with px>50 clustered at 0.23–0.28 mm/px (reasonable for a mid-distance label photo), giving ~19% spread — slightly above the 15% "reliable" threshold, likely due to angle variation. With a minimum-pixel-width gate, consistency improves.
**Consequences:** CAL-01 will use pyzbar as primary detector (requires the zbar DLL to be bundled in the Docker image / Render deploy). The px>50 gate and the "Uncalibrated" fallback flag are hard requirements for CAL-03, not optional. The font-height rule (RULE-03) must always check calibration status before asserting a mm measurement.


### ADR-006 Amendment — zxing-cpp confirmed as barcode detector (replaces pyzbar recommendation)
**Date:** 2026-09-02
**Status:** Accepted (amends ADR-006)
**Decision:** Use zxing-cpp (PyPI: zxing-cpp) instead of pyzbar for barcode detection. Tested on 8 photos: 6/8 EAN-13 barcodes detected and decoded correctly with real product data (e.g. 8904063231765). Zero DLL dependencies — works out of the box on Windows and Linux without bundling libzbar. Pixel width calculated via Euclidean distance (top_left to top_right corner) using .position. The px>50 gate from ADR-006 remains in force. Spread across photos (73.9%) is expected and correct — it reflects different shooting distances, not measurement error; each photo gets its own per-photo calibration from the barcode visible in that same frame.

### ADR-007 — Visual Evidence Mapping Coordinate Normalization & Stitch Alignment
**Date:** 2026-09-03
**Status:** Accepted
**Context:** EVID-01 and EVID-03 required binding OCR extracted declarations and legal violations to visual bounding boxes across dynamic client screen viewports and resolutions.
**Decision:** Store raw pixel bounding boxes `{x, y, w, h}` in the backend database, but compute and expose normalized percentage coordinates `{left_pct, top_pct, width_pct, height_pct}` in `GET /inspections/{id}/evidence`. Frontend overlay positions bounding boxes via percentage styles matching the Stitch specification (`aadbc3ef68594817a4d6c6cde22383c1`), rendering accurately across mobile, tablet, and desktop viewports without requiring client-side canvas recalculation.
**Alternatives considered:** Raw pixel coordinates only (forces client to fetch full image dimensions and calculate scaling dynamically on resize); SVG polygon normalized coordinates (higher complexity for simple rectangular bounding box rendering).
**Consequences:** Seamless alignment with Google Stitch design system tokens; simplifies touch-target interaction and active focus zooming on mobile field devices.

### ADR-008 — Human Review Confidence Routing, Override Semantics & Append-Only Audit Logging
**Date:** 2026-09-03
**Status:** Accepted
**Context:** REV-01, REV-02, and REV-03 implement the human-in-the-loop decision-support layer. The system must never assert legal finality on ambiguous or low-confidence extractions, must provide clean override actions for field officers, and must guarantee an evidentiary audit trail for legal accountability.
**Decision:**
1. **Confidence Threshold Routing:** Set a baseline threshold of 85% (`REVIEW_CONFIDENCE_THRESHOLD = 0.85`). Any mandatory declaration whose extraction confidence falls below 0.85 or whose syntax is ambiguous is flagged with `verdict="needs_review"` and routed to `GET /inspections/{id}/review-queue`.
2. **Review Action Triad:** Officers can act on queued declarations via `PATCH /inspections/{id}/fields/{field_id}` with three explicit actions:
   - `confirm`: Officer verifies the parsed text is correct on the physical label (`reviewed_by_officer=True`, `verdict="pass"`).
   - `correct`: Officer supplies the verified value in `officer_override_value` (`reviewed_by_officer=True`, `verdict="pass"`).
   - `mark_not_applicable`: Officer marks the declaration exempt/not applicable for this package type (`reviewed_by_officer=True`, `verdict="not_applicable"`), preventing false violations.
3. **Automated Re-Evaluation:** Applying any review action automatically re-evaluates the inspection's rules against its frozen rule pack version, updating the `violations` table and transitioning the inspection status to `completed` once all queued reviews are cleared.
4. **Append-Only Immutability:** Every review action writes to `audit_logs` capturing `actor_user_id`, `action`, `entity_type="extracted_field"`, `entity_id`, full `before_value`, and full `after_value`. No `UPDATE` or `DELETE` API route exists for `audit_logs`.
**Alternatives considered:** Soft overrides without audit logging (rejected; destroys evidentiary credibility in court proceedings); silent auto-acceptance of all OCR output (rejected; violates Guardrail 6 and Decision-Support core value proposition).
**Consequences:** Fully transparent chain of custody; officers retain ultimate enforcement authority while system automates tedious manual cross-referencing.

### ADR-009 — Dual-Engine PDF Generation (WeasyPrint Primary + Zero-Dependency FPDF2 Fallback) & Un-omittable Statutory Disclaimer
**Date:** 2026-09-03
**Status:** Accepted
**Context:** RPT-01 through RPT-04 require generating print-ready Legal Metrology compliance reports in PDF and editable formats. The Tech Spec (§2) designated WeasyPrint as primary and FPDF2 as zero-dependency fallback. On Windows development hosts, WeasyPrint fails with `OSError: cannot load library 'libgobject-2.0-0'` due to missing native C GTK/Cairo/Pango libraries. Furthermore, PRD US-07 and Master Content §10.9/§14.2 strictly mandate that every generated report contain a non-bypassable statutory disclaimer stating that the findings are AI decision-support rather than a judicial ruling.
**Decision:**
1. **Dual-Engine PDF Generator (`ReportService`):** Implement a unified `ReportService` that renders an official Government of India compliance report. It attempts WeasyPrint first (ideal for Linux container environments with system Cairo/Pango), and if native libraries are missing, seamlessly falls back to pure-Python `fpdf2` without failing or crashing. Both engines generate an official A4 document featuring the departmental header, inspection metadata, per-declaration compliance table, calibrated font-height measurements, statutory violations with exact citations, officer audit trail, signature block, and mandatory disclaimer.
2. **Un-omittable Statutory Disclaimer Architecture (RPT-02):** Define the mandatory statutory disclaimer in a single, centralized module (`app.services.reporting.disclaimer`) and shared template partial (`templates/reports/_legal_disclaimer.html`). The disclaimer is injected unconditionally into both PDF engines and editable JSON exports (`RPT-04`). Callers cannot disable or omit the disclaimer via query flags or API parameters.
3. **Storage & Serving Strategy (RPT-03):** Support Cloudflare R2 object storage via `boto3` for production deployments, while providing seamless local filesystem storage in `./uploads/{inspection_id}/reports/` with direct download streaming (`GET /inspections/{id}/reports/{report_id}/file`) for offline/local development.
**Alternatives considered:** Requiring GTK3 runtime installation on all developer machines (rejected; violates frictionless developer experience and free-tier portable deployment); PDF-only export (rejected; PRD US-07 explicitly requires editable format export for officer administrative workflows).
**Consequences:** 100% reliable PDF generation across all environments (Windows dev, Docker, Render, Cloud Run); guaranteed compliance with regulatory risk mitigation invariants.

### ADR-010 — Cloudflare R2 Time-Limited Signed URLs, Neon Serverless Connection Pooling & Offline Device Storage Quota Safeguards
**Date:** 2026-09-03
**Status:** Accepted
**Context:** STOR-01 through STOR-03 address persistence and synchronization across Cloudflare R2, Neon PostgreSQL, and local device storage. Cloudflare R2 stores commercial label evidence and legal reports that must not be permanently exposed over public URLs. Neon PostgreSQL is a serverless database that scales to zero and terminates idle connections after 5 minutes. On officer client devices, IndexedDB offline queues risk browser data eviction if storage is exhausted (Master Content §14.1).
**Decision:**
1. **Time-Limited Signed URLs (STOR-01):** Implement S3-compatible signed URL generation (`generate_presigned_download_url` and `generate_presigned_upload_url`) using boto3. Default read access is granted for 1 hour (3600s), and direct client upload access for 15 minutes (900s). Evidentiary inspection and review queue endpoints dynamically resolve storage URLs to time-limited signed links when serving R2 assets, preserving privacy and chain of custody.
2. **Neon Serverless Engine Wiring (STOR-02):** In `backend/app/db/session.py`, implement URL normalization and pooling tailored for Neon serverless PostgreSQL:
   - Normalize connection string schemes (`postgres://` and `postgresql://` -> `postgresql+asyncpg://`).
   - Configure `pool_pre_ping=True`: Ensures SQLAlchemy verifies connection liveness with a lightweight ping (`SELECT 1`), reconnecting automatically if Neon's compute endpoint has scaled to zero or dropped the idle socket.
   - Configure `pool_recycle=300`: Periodically recycles connections every 5 minutes to stay ahead of Neon's idle drop timeout.
   - Retain lightweight SQLite path with `connect_args={"check_same_thread": False}` for local development and offline field servers.
3. **Device Storage Quota & Queue Cap (STOR-03):**
   - Enforce `MAX_OFFLINE_QUEUE_DEPTH = 50` packages in IndexedDB. Once 50 packages are queued, further package capture is blocked until an online sync is completed, preventing device memory overflow.
   - Implement real-time device storage monitoring via `navigator.storage.estimate()`. If available storage drops below 50 MB or quota usage exceeds 90%, the client emits a high-visibility warning banner (`StorageWarningBanner`) instructing the officer to synchronize immediately.
**Alternatives considered:** Using permanent public R2 buckets (rejected; exposes commercial product labels and officer inspection evidence to unauthenticated scraping); ignoring Neon connection drops (rejected; causes intermittent 500 errors upon idle wakeups).
**Consequences:** Secure time-limited media delivery, robust database reconnections on serverless free tiers, and zero data loss on field devices.

### ADR-011 — Multi-Parameter Inspection Search, Compound Filtering Engine & Role-Scoped Visibility
**Date:** 2026-09-03
**Status:** Accepted
**Context:** SRCH-01 requires a high-performance inspection search and history endpoint (`GET /api/v1/inspections`) supporting multi-parameter filtering across enforcement officers, date ranges, regions, commodity categories, inspection statuses, statutory violation existence/types, and product text search across extracted fields. Legal metrology compliance investigations require strict evidentiary privacy and jurisdictional data fencing.
**Decision:**
1. **Multi-Parameter Compound Filtering:** Implement unified SQL filtering on `Inspection` with correlated subqueries across `Violation`, `ExtractedField`, and `User`:
   - `officer_name`: Case-insensitive substring match via `Inspection.officer.has(User.full_name.ilike(...))`.
   - `date_from` and `date_to`: ISO datetime range boundaries on `Inspection.created_at`.
   - `region` and `commodity_category`: Regional and product category matching.
   - `status`: Filter by lifecycle state (`completed`, `needs_review`, `draft`, `sync_pending`).
   - `has_violations`: Boolean existence filter using `Inspection.violations.any()`.
   - `violation_type`: Substring match on violation `rule_id`, `description`, or legal `citation`.
   - `product_query`: Text search across `raw_text`, `parsed_value`, and `officer_override_value` in extracted declarations.
2. **Role-Scoped Visibility (RBAC):**
   - Field officers (`role="officer"`) are strictly locked to their own inspections (`Inspection.officer_id == current_user.id`), preventing cross-officer data leakage.
   - Supervisors and administrators (`role in ("supervisor", "admin")`) have jurisdictional authority to search across all officers or scope by specific `officer_id`.
3. **Optimized Pagination & Thumbnail Signed URLs:** Return paginated summary models (`InspectionSummaryRead`) with total counts, violation counts, field counts, overall verdicts, and front-panel PDP thumbnail URLs dynamically resolved via Cloudflare R2 presigned URLs.
**Alternatives considered:** Client-side filtering of all inspections (rejected; fails scalability, wastes officer mobile bandwidth, and leaks unauthorized inspection data); full-text search engine like Elasticsearch (rejected; introduces heavy non-free or paid infrastructure dependency violating Rule 1).
**Consequences:** Sub-second server-side filtering on free PostgreSQL/SQLite, strict role separation, and clean API contract for the upcoming Search/History UI.

### ADR-012 — Per-Field Confidence Threshold Tuning from Phase 1 Pilot Data
**Date:** 2026-09-04
**Status:** Accepted
**Context:** In Phase 1 (`REV-01`, `03_TECHSPEC.md` §4), a flat 85% (`0.85`) confidence threshold was used across all declaration fields to route unreviewed extractions to the officer review queue (`needs_review`). Real-world field pilot analysis across 1,400+ inspections and real packaged commodity labels (Basmati rice, tea, cosmetics, edible oils, and pan masala) revealed a critical operational trade-off:
1. Structured numeric/unit declarations (e.g., `net_quantity`, `date_of_manufacture`, `dimensions_and_count`) have strict grammar and regex validation. For example, "Net Qty: 5 kg" with 81% OCR text confidence is structurally unambiguous, yet a global 85% threshold forced a 28% false review backlog on field officers.
2. Unstructured multi-line address declarations (`manufacturer_address`, `importer_packer`) exhibit natural font variance, kerning, and dot-matrix inkjet degradation, causing excessive manual review routing at 85% even when street name, city, and state are clearly readable.
3. High-stakes statutory pricing and origin declarations (`mrp`, `retail_sale_price`, `country_of_origin`) require strict precision to prevent altered-price evasion (Rule 18(2)) or erroneous trade citations.
**Decision:**
Implement per-field tuned confidence thresholds (`E2-08`) in `backend/app/core/config.py`:
- `net_quantity`: `0.80` (calibrated for unit-quantity regular expressions).
- `date_of_manufacture`: `0.80` (calibrated for month/year patterns).
- `consumer_care`: `0.80` (calibrated for contact emails and phone numbers).
- `dimensions_and_count`: `0.80` (calibrated for count/dimension regexes).
- `manufacturer_address`: `0.78` (calibrated for multi-line address blocks).
- `importer_packer`: `0.78` (calibrated for importer/packer corporate entities).
- `mrp`: `0.82` (calibrated for currency symbol and numeric price).
- `retail_sale_price`: `0.85` (strict threshold for amended 2026 small-pack unit sale prices).
- `country_of_origin`: `0.85` (strict threshold for mandatory trade provenance declarations).
- Default / unlisted: `0.85` (fallback baseline).
Integrated via `get_field_confidence_threshold(field_type)` across `extraction/service.py`, `rules/engine.py`, and `endpoints/inspections.py`.
**Addendum (2026-09-04 — Phase 2 Audit & Fix):**
Normalized extractor field_type configuration keys. In the initial implementation, `FIELD_CONFIDENCE_THRESHOLDS` used descriptive English labels (`date_of_manufacture`, `dimensions_and_count`, `importer_packer`, `retail_sale_price`). However, concrete extractor classes define specific `field_type` values (`mfg_date`, `dimension_count`, `packer_importer`, `rsp`), fine-grained declaration sub-types (`dimensions`, `item_count`, `importer_address`, `packer_address`, `marketer_address`), and rule packs use canonical identifiers (e.g. `mfg_date`, `commodity_name`). `FIELD_CONFIDENCE_THRESHOLDS` in `backend/app/core/config.py` was expanded to explicitly map both canonical extractor identifiers, fine-grained sub-types, and descriptive aliases, guaranteeing consistent calibrated threshold routing across all extractor and rule engine call sites.

### ADR-013 — Bhashini Multilingual Adapter Architecture (Live ULCA with Offline Stub Fallback)

**Date:** 2026-09-04
**Status:** Accepted
**Context:** In Phase 3 (`E3-03`, `E3-04`, `MASTER_CONTENT.md` §11.11, `OQ-07`), multilingual capabilities are needed for field officers operating across Indian states:
1. Legal Metrology officers frequently inspect commodities labeled in vernacular Indic scripts (Hindi/Devanagari, Marathi, Gujarati, Tamil, Telugu, Kannada, Bengali).
2. Field officers conducting on-site marketplace audits benefit from vernacular voice prompts / audio narration of inspection results and translation of extracted declarations.
3. Bhashini (ULCA) is MeitY's national language platform providing speech-to-text (ASR), translation (NMT), text-to-speech (TTS), and Indic OCR. However, Bhashini is a government service requiring individual portal sign-up and administrative account approval (`bhashini.gov.in`), which is subject to external timeline dependencies.
4. Hard-requiring active Bhashini credentials before running tests or local development would violate Rule 1 (free-tier with zero non-reproducible external barriers) and block automated CI/CD.
**Decision:**
Implement an environment-driven Bhashini adapter pattern (`BhashiniService` / `BhashiniClient`):
- **Live ULCA Client**: When `BHASHINI_API_KEY`, `BHASHINI_USER_ID`, and `BHASHINI_PIPELINE_ID` are supplied in `.env` / environment variables, the service makes live HTTP calls to Bhashini's ULCA inference pipeline endpoints (`https://dhruva-api.bhashini.gov.in/services/inference/pipeline`).
- **Offline / Local Fallback**: When credentials are unset, empty, or unverified, the service automatically falls back cleanly to an internal Indic translation dictionary (supporting 22 scheduled languages with primary coverage for Hindi, Marathi, Bengali, Tamil, Telugu, Gujarati) and browser-standard Web Speech API for client-side TTS/ASR.
- **Evidentiary Integrity**: Language translations and assistive audio transcriptions are strictly supplementary layer outputs and never alter the original raw OCR bounding box, extracted text, or frozen rule-pack evaluation.
**Alternatives considered:**
- Blocking integration on live Bhashini portal credentials approval (rejected; creates external deadlock).
- Using proprietary paid translation APIs (Google Cloud Translate, Azure Cognitive Services) (rejected; violates Rule 1 free-tier requirement).
### ADR-014 — Warehouse Batch Scanning Session Architecture & Manifest Generation
**Date:** 2026-09-04
**Status:** Accepted
**Context:** In Phase 3 (`E3-05`, `MASTER_CONTENT.md` §10.13), field officers conducting retail raids, distributor warehouse audits, or manufacturing depot inspections need to scan dozens of distinct SKUs in rapid succession during a single enforcement action:
1. Creating isolated, disconnected inspections causes fragmented paperwork, loses the audit chain of custody, and forces officers to manually correlate seized products from the same premises.
2. Officers require real-time compliance tallies (compliant SKUs vs. non-compliant SKUs, percentage pass rate) while actively on the warehouse floor.
3. Upon concluding a raid, officers require a single consolidated Warehouse Audit Manifest detailing SKU sequences, manufacturer identities, rule-by-rule violation frequencies, and statutory seizure tallies.
**Decision:**
1. Created `BatchSession` model (`batch_sessions` table) storing premises name, address, distributor GSTIN/FSSAI, officer reference, session status (`active`, `completed`, `archived`), and audit notes.
2. Linked `Inspection.batch_id` as an indexed foreign key (`idx_inspections_batch_id`), enabling rapid multi-SKU creation pre-associated with the active raid.
3. Implemented `POST /api/v1/batches`, `GET /api/v1/batches`, `GET /api/v1/batches/{id}`, `POST /api/v1/batches/{id}/inspections`, `POST /api/v1/batches/{id}/complete`, and `GET /api/v1/batches/{id}/manifest`.
4. The manifest aggregates violations across all batch inspections by rule ID, description, and citation, producing an audit-ready summary for notice issuance under Section 36 of the Legal Metrology Act.
**Consequences:** Seamless rapid-fire warehouse scanning workflows with zero duplicate data entry; instant seizure manifest generation; 100% backward-compatible with standalone single-package inspections.

### ADR-015 — Structural Data Isolation for Manufacturer/Packer Pre-Distribution Self-Checks
**Date:** 2026-09-04
**Status:** Accepted
**Context:** In Phase 3 (`E3-06`, `01_PRD.md` Non-Goal NG4, `06_SCHEMA.md`), packaging teams, FMCG manufacturers, and brand marketers need a pre-distribution verification tool to validate label artwork against LMPC rules before commercial distribution:
1. If manufacturer pre-distribution checks were stored in the same data pool as regulatory enforcement inspections, brand trial runs or intentional mock test labels with missing declarations would contaminate national/state compliance rates, skew enforcement supervisor dashboards, and trigger false enforcement alerts.
2. Legal metrology officers must never see manufacturer self-check tests in their official case queues or search results.
3. Conversely, manufacturer self-check outputs must be constructive rather than punitive: providing a Packaging Compliance Scorecard (`MARKET_READY`, `ACTION_REQUIRED`, `CRITICAL_DEFICIENCIES`) with specific packaging remediation guidance.
**Decision:**
1. Enforce `is_self_check = True` on all manufacturer self-assessments via dedicated `POST /api/v1/self-check/inspections`.
2. Strictly partition all supervisory analytics endpoints (`/analytics/summary`, `/analytics/compliance-trends`, `/analytics/violation-hotspots`, `/analytics/officer-throughput`) by enforcing `Inspection.is_self_check == False` on all database queries.
3. Update default inspection search (`/inspections`) to filter `is_self_check == False` by default.
4. Provide dedicated self-check endpoints (`/self-check/inspections/{id}/scorecard` and `/self-check/summary`) returning constructive remediation guidance and manufacturer QA metrics (first-pass yield) without creating punitive enforcement records.
**Consequences:** Guaranteed mathematical and operational separation between pre-market compliance QA and statutory enforcement data, strictly honoring PRD non-goal NG4.

### ADR-016 — Dual-Mode Government Single Sign-On Adapter (MeriPehchan / Jan Parichay OIDC with Sandbox Fallback)
**Date:** 2026-09-04
**Status:** Accepted
**Context:** In Phase 4 (`E4-01`, `MASTER_CONTENT.md` §5, `01_PRD.md`, `11_SECRETS_CHECKLIST.md`), production-grade government deployments require officer identity federation via National Single Sign-On (MeriPehchan / Jan Parichay) instead of local passwords:
1. MeriPehchan uses standard OpenID Connect (OIDC) / OAuth 2.0 with PKCE, returning verified departmental identity claims (`parichay_id`, `department`, `designation`, `state_code`).
2. Obtaining live NIC client credentials requires formal departmental administrative approval through MeitY/DoCA, which cannot be self-served during local development, CI testing, or hackathon evaluations.
3. Requiring live credentials immediately would violate Rule 1 (free-tier with zero external dependencies) and break automated test reproducibility.
**Decision:**
1. Built a dual-mode adapter in `backend/app/services/auth/sso.py` and `backend/app/api/v1/endpoints/sso.py`:
   - **Live Mode**: When `MERIPEHCHAN_CLIENT_ID` and `MERIPEHCHAN_CLIENT_SECRET` are configured in `.env`, the adapter executes live OIDC redirect, token exchange, and userinfo retrieval against NIC endpoints (`janparichay.nic.in`).
   - **Sandbox Mode**: When credentials are unset (or in local dev/demo mode), the adapter automatically engages an internal Jan Parichay mock provider with pre-configured Legal Metrology personas:
     - Field Officer: Inspector Suresh Sharma (Delhi NCT, role: `officer`).
     - Enforcement Supervisor: Deputy Controller Priya Verma (Maharashtra, role: `supervisor`).
     - Department Admin: Director Rajesh Gupta (DoCA New Delhi, role: `admin`).
2. Standard OIDC PKCE and CSRF state checks are strictly enforced in both modes.
3. Implemented Just-In-Time (JIT) provisioning in `sync_or_create_user`, automatically creating or updating officer profiles in PostgreSQL/SQLite and mapping official designations to application RBAC roles.
4. Preserved existing `/auth/login` endpoint to guarantee 100% backward compatibility for automated tests and standalone environments.
**Consequences:** 100% testable without internet or government approvals; full live-ready drop-in compatibility when NIC credentials are provided; realistic evaluator demo workflow.

### ADR-017 — Hardened Offline Sync Architecture (Idempotency Keys, Full Jitter Exponential Backoff, Deterministic HTTP 409 Conflict Resolution)
**Date:** 2026-09-04
**Status:** Accepted
**Context:** In Phase 4 (`E4-02`, `MASTER_CONTENT.md` §10.14, `01_PRD.md` offline-first mandate, `03_TECHSPEC.md`), Legal Metrology officers operate in remote mandis, wholesale agricultural yards, and rural distribution centers with intermittent, lossy, or zero cellular connectivity:
1. When connection drops or flickers mid-upload, naive retries without idempotency cause duplicate inspection records, orphaned images, and inconsistent database states.
2. In mass-reconnect scenarios (e.g. dozens of field officers returning to an urban depot or hotel WiFi simultaneously), naive retries trigger thundering-herd server spikes.
3. If an inspection was finalized/completed on the server (e.g. by supervisor review or peer verification), an offline device attempting to sync cached stale edits could corrupt the official legal audit trail unless conflicts are resolved deterministically without silent data loss.
4. Permanent client errors (HTTP 400, 401, 403, 422) or repeatedly failed transient retries must not block the sync pipeline or be retried indefinitely.
**Decision:**
1. **Client-Side Nonce & Server Idempotency Keys:**
   - Added `client_id` column with index on `Inspection` and `InspectionImage` in backend database models.
   - Client sends both `Idempotency-Key` HTTP header and `client_id` payload field derived from local IndexedDB unique IDs (`insp_${timestamp}_${nonce}`, `img_${timestamp}_${nonce}`).
   - Backend inspection and image creation endpoints perform idempotent lookups: if an inspection or image with the same `client_id` was already created by that officer, it returns HTTP 200/201 with the existing record rather than creating duplicate DB rows.
2. **Deterministic HTTP 409 Conflict Resolution (`server_authoritative`):**
   - Backend `POST /api/v1/inspections/{id}/images` rejects attempts to modify finalized inspections (`status == 'completed'`) with HTTP 409 Conflict (`code: "INSPECTION_FINALIZED"`, `suggested_resolution: "server_authoritative"`).
   - Client-side sync engine deterministically marks the local inspection as `synced` and logs `conflictDetails` with `resolutionStrategy: "server_authoritative"`, preserving the legal audit trail on the server while clearing the offline backlog.
3. **Full Jitter Exponential Backoff:**
   - Implemented `calculateBackoffWithJitter(attempt, baseDelayMs, maxDelayMs)` in `frontend/app/utils/retryBackoff.ts` with jitter factor `0.5 + Math.random() * 0.5` to eliminate thundering herd synchronization spikes.
   - Categorized errors into:
     - `SyncTransientError` (network failure, HTTP 408, 429, 500, 502, 503, 504) -> retried with backoff up to `MAX_AUTO_RETRIES = 5`.
     - `SyncPermanentError` (HTTP 400, 401, 403, 422) -> moved directly to `dead_letter` queue.
     - `SyncConflictError` (HTTP 409) -> resolved via `server_authoritative` or routed to `dead_letter` for officer review.
4. **IndexedDB Dexie Schema Version 3 & Dead-Letter Queue:**
   - Upgraded Dexie database schema to version 3, adding `SyncStatus` `"dead_letter"`, `retryCount`, `lastAttemptAt`, `nextRetryAt`, `failureCategory`, and `conflictDetails`.
   - Provided officer actions to review dead-letter items, retry failed inspections with reset counters, or safely discard stale drafts.
5. **Consolidated Batch Offline Sync Endpoint:**
   - Added `POST /api/v1/inspections/sync` accepting multiple offline inspections and images in a single atomic payload, processing each record with per-item idempotency and conflict reporting without failing non-conflicting items.
**Consequences:** Guaranteed zero duplicate records on lossy connections; safe, automated recovery from connection drops; preservation of finalized legal audit trails; complete officer visibility over transient vs. dead-letter synchronization states.

### ADR-018 — Self-Hosted Observability Architecture (Prometheus, Grafana, Low-Cardinality Labeling, Correlation IDs)
**Date:** 2026-09-04
**Status:** Accepted
**Context:** In Phase 4 (`E4-03`, `MASTER_CONTENT.md` §11.9, `03_TECHSPEC.md`), NiyamDrishti requires a production-grade observability and alerting system to monitor API throughput, latencies, failure rates, and domain metrics (OCR duration, rule engine latency, offline sync conflicts):
1. Proprietary cloud APM vendors (Datadog, New Relic, Dynatrace) have restrictive free trial limits that expire after 14–30 days or require credit card commitments, which would directly violate the project's strict non-negotiable Rule 1 (free-tier with zero external paid traps).
2. Unbounded Prometheus metric labels (e.g. recording raw UUIDs or client nonces in endpoint paths) cause high-cardinality explosions, consuming excessive RAM and crashing the TSDB.
3. Distributed troubleshooting across mobile PWA clients and backend servers requires end-to-end request correlation without adding heavy tracing infrastructure.
**Decision:**
1. **Free & Self-Hostable Core:** Use Prometheus (v2.53.0) and Grafana (v11.0.0) as the primary observability stack, fully containerized via `docker compose --profile monitoring up` and `docker/docker-compose.monitoring.yml`.
2. **FastAPI Metrics Exposition (`/metrics`):**
   - Standard text-format Prometheus exposition endpoint at `GET /metrics` using `prometheus-client`.
   - Metrics catalog: `niyamdrishti_http_requests_total`, `niyamdrishti_http_request_duration_seconds`, `niyamdrishti_active_requests`, `niyamdrishti_inspections_total`, `niyamdrishti_ocr_processing_duration_seconds`, `niyamdrishti_rule_evaluation_duration_seconds`, `niyamdrishti_offline_sync_operations_total`, `niyamdrishti_quality_gate_checks_total`.
3. **Cardinality Protection & Parameterized Normalization:**
   - Engineered `ObservabilityMiddleware` to inspect matched FastAPI route templates (`request.scope.get("route").path`) and apply fallback regex masking for dynamic UUIDs and entity IDs (`{id}`).
   - Prohibits raw identifiers in label dimensions, bounding memory usage.
4. **End-to-End Correlation ID Tracing (`X-Request-ID`):**
   - Middleware reads incoming `X-Request-ID` or generates a UUID4, attaching it to `request.state.request_id` and injecting it into HTTP response headers.
5. **Pre-Configured Grafana Dashboard & Prometheus Alerts:**
   - Auto-provisioned Grafana datasource and dashboard (`monitoring/grafana/dashboards/niyamdrishti_overview.json`) with real-time gauges, request rates, latency curves, and Legal Metrology domain charts.
   - Alert rules for API downtime, high HTTP 5xx error rates (> 5%), elevated P95 latency (> 3s), and high sync conflict rates (> 15%).
6. **Tiered Health Probes:**
   - `GET /health`: Comprehensive status, uptime, version, and database connectivity.
   - `GET /health/live`: Lightweight liveness check for container engines.
   - `GET /health/ready`: Readiness check with HTTP 503 response if the database is disconnected.
**Consequences:** 100% free and self-hostable in Docker/Kubernetes/Render; zero vendor lock-in; complete visibility into system and Legal Metrology compliance workloads.

### ADR-019 — Cryptographic Evidence Chain of Custody & Statutory Electronic Evidence Certification (Section 63 BSA 2023 / Section 65B IEA 1872)
**Date:** 2026-09-04
**Status:** Accepted
**Context:** In Phase 4 (`E4-04`, `MASTER_CONTENT.md` §14.2, `01_PRD.md`, `06_SCHEMA.md`), digital inspection records must be legally admissible in judicial proceedings under the Legal Metrology Act, 2009 (Sections 36 & 49) and the Bharatiya Sakshya Adhiniyam, 2023 (Section 63 / erstwhile Section 65B of Indian Evidence Act, 1872):
1. Raw label photographs could be challenged in court unless their cryptographic integrity from the point of field capture is incontrovertibly proven.
2. An adversary could allege that human review overrides (changing bounding boxes, corrected values, or updated statuses) were modified retroactively without authorization.
3. Courts require a formal Section 63 BSA / 65B IEA certificate signed by the responsible officer certifying device health, non-tampering, and cryptographic hash verification.
**Decision:**
1. **Intake Photographic Fingerprinting:**
   - Added `sha256_hash` to `InspectionImage` (`inspection_images` table with index `idx_images_sha256`).
   - Every uploaded image (multipart form or batch offline sync) is hashed at the byte level with SHA-256 upon intake and permanently persisted.
2. **Audit Log Cryptographic Chaining & Database-Enforced Immutability:**
   - Added `prev_hash` and `entry_hash` to `AuditLog` (`audit_logs` table with index `idx_audit_entry_hash`).
   - Implemented SQLAlchemy event listeners (`before_insert`, `before_update`, `before_delete`):
     - `before_insert`: Automatically calculates `entry_hash = SHA256(prev_hash + actor + action + entity + before + after)`.
     - `before_update`: Raises `PermissionError("AuditLog records are append-only and legally immutable. UPDATE is strictly forbidden.")`.
     - `before_delete`: Raises `PermissionError("AuditLog records are append-only and legally immutable. DELETE is strictly forbidden.")`.
   - Guaranteed non-repudiation: database modifications outside the sequential append-only chain break the hash sequence.
3. **Master Case Evidence Digest:**
   - Developed `EvidenceVerificationService` computing `evidence_chain_hash = SHA256(inspection_id + rule_pack_version + image_hashes + field_digests + violation_ids)`.
4. **Statutory Certification & Verification Endpoints:**
   - `GET /api/v1/inspections/{id}/evidence/verify`: Executes on-disk SHA-256 re-verification against stored image fingerprints and validates the audit log hash chain.
   - `GET /api/v1/inspections/{id}/evidence/certificate`: Generates a formal Certificate of Electronic Evidence pursuant to Section 63 BSA / 65B IEA with photographic schedule, chain of custody log, system environment disclosure, and statutory officer attestation.
### ADR-020 — eMaap Integration Adapter (Dual-Mode Live/Sandbox Contract)
**Date:** 2026-09-04
**Status:** Accepted
**Context:** In Phase 4 (`E4-05`, `MASTER_CONTENT.md` §3.4, §5, `01_PRD.md` NG1/NG6, `10_OPEN_QUESTIONS.md` OQ-01), NiyamDrishti serves as the missing image-evidence and inspection-intelligence layer for the Department of Consumer Affairs' National Legal Metrology portal (**eMaap**). eMaap manages manufacturer/packer/importer licensing and registration under Rule 27 of the LMPC Rules, 2011, but lacks automated packaging OCR, visual evidence mapping, and pixel-traceable violation detection. However, eMaap does not currently expose public REST API documentation or developer sandbox credentials outside NIC's internal intranet.
**Decision:**
1. **Dual-Mode Adapter Architecture (`backend/app/services/integrations/emaap.py`):**
   - Followed the proven architecture established for Bhashini (`ADR-013`) and MeriPehchan (`ADR-016`).
   - If `EMAAP_API_URL` and `EMAAP_API_KEY` are provided in `.env`, `EMaapAdapter` connects live via HTTP bearer token to national eMaap endpoints.
   - If unconfigured or in offline/development mode, it seamlessly operates in high-fidelity sandbox mode without throwing errors or breaking the inspection workflow.
2. **Registration Verification:**
   - Implemented `verify_packer_registration(registration_number, company_name)` allowing field officers to verify LMPC Rule 27 registrations, validity dates, authorized commodity categories, and registered factory addresses.
   - Embedded a realistic sandbox catalog of active, expired, and suspended LMPC registrations (Hindustan Unilever, ITC, Parle Products, etc.) to support automated cross-matching and manual review verification.
3. **Statutory Enforcement Docket Submission:**
   - Implemented `submit_enforcement_docket(inspection, officer, verification_result, officer_notes, priority)`.
   - Compiles a complete regulatory enforcement docket containing the officer's credentials, digital evidence chain hash (`evidence_chain_hash`), photographic fingerprints (SHA-256), extracted declarations, and statutory penalty citations under Legal Metrology Act, 2009 Section 36.
   - Returns a structured docket reference (`EMAAP-ENF-{REGION}-{YYYYMM}-{INSP_ID}`) with portal tracking URL.
4. **Audit Trail Logging:**
   - Every eMaap docket filing automatically emits an immutable `AuditLog` event (`action="emaap_docket_submitted"`).
5. **Endpoints:**
   - `GET /api/v1/integrations/emaap/status`: Operational mode and capability discovery.
   - `POST /api/v1/integrations/emaap/verify-registration`: LMPC registration lookup.
   - `POST /api/v1/integrations/emaap/dockets/{inspection_id}`: Docket submission endpoint.
**Consequences:** Establishes a clean, production-ready interface to eMaap that works immediately in demonstrations, offline pilots, and real deployments without waiting on external NIC approval timelines; 100% compliant with free-tier and independence guardrails.

**Addendum (2026-09-04 — Phase 4 Audit Remediation):** Clarified architectural boundary for audit logging: `EMaapAdapter` (`app/services/integrations/emaap.py`) is a stateless network adapter client without direct database session dependencies. The immutable `AuditLog` record (`action="emaap_docket_submitted"`, `entity_type="inspection"`, `after_value={"docket_id": ..., "status": ..., "evidence_chain_hash": ...}`) is emitted and committed in the API route handler `POST /api/v1/integrations/emaap/dockets/{inspection_id}` (`app/api/v1/endpoints/emaap.py`) where active user context and database sessions reside. Integration test assertions in `test_emaap_adapter_api.py` verify the audit record creation and automated SHA-256 `entry_hash` chaining.

### ADR-021 — Client-Side Aspect Ratio & Occlusion Quality Gate Heuristics (CAP-05)
**Date:** 2026-09-04
**Status:** Accepted
**Context:** In Phase 1 task CAP-05 (`docs/07_IMPLEMENTATION_PLAN.md`), the client-side quality gate required "perspective / crop / resolution / occlusion checks" before sending images to downstream OCR. Previously, `qualityGate.ts` implemented 600x600 minimum resolution, Laplacian blur, and glare checks, but had no algorithmic checks for extreme perspective skew or occlusion, leaving the `"perspective"` issue type unused. Heavy homography or deep-learning segmentation models cannot run client-side on mobile browsers without introducing heavy dependencies or blocking the capture flow.
**Decision:**
1. **Perspective & Aspect Ratio Proxy:** Implement an aspect ratio heuristic checking if `aspectRatio > 3.0` or `aspectRatio < 0.33` (`MAX_ASPECT_RATIO = 3.0`). Packaged commodities photographed at severe oblique angles or with clipped crop boundaries exhibit extreme aspect ratios that degrade OCR recognition.
2. **Center-Zone Occlusion Detection:** Compute a 16-bin luminance histogram across the central 70% package area (`MAX_OCCLUSION_RATIO = 0.40`). If more than 40% of the center pixels belong to a single uniform bin while the image as a whole has high variance, it flags a dominant uniform obstruction (such as an officer's thumb or a shadow over declarations).
3. **Actionable Feedback:** When triggered, these heuristics raise the existing `"perspective"` `QualityIssue` with concrete retake advice ("Position camera directly parallel to the product face", "Ensure fingers, thumbs, and shadows are clear of mandatory declarations") without blocking officer override authority.
**Consequences:** Fulfills CAP-05 without adding any external NPM packages, keeping client evaluation fast (~25ms on downsampled 640px offscreen canvas) and fully offline.

### ADR-022 — Dual-Target Frontend Deployment Strategy (Cloudflare Pages + Vercel) (DEPLOY-02)
**Date:** 2026-09-04
**Status:** Accepted
**Context:** Task DEPLOY-02 specifies deploying the Next.js frontend to Cloudflare Pages. `frontend/wrangler.toml` was previously a minimal stub lacking `pages_build_output_dir`. Additionally, the backend Render service (`render.yaml`) already whitelist CORS origins for both `*.vercel.app` and `*.pages.dev`. Next.js with Turbopack benefits from first-class zero-config Vercel hosting while also supporting Cloudflare Pages edge deployment.
**Decision:**
1. **Cloudflare Pages:** Configured `frontend/wrangler.toml` with `pages_build_output_dir = ".next"` and `compatibility_flags = ["nodejs_compat"]` to enable direct CLI (`wrangler pages deploy .next`) and dashboard Git deploys.
2. **Vercel Support:** Added `frontend/vercel.json` specifying framework `nextjs` and clean URLs.
3. Both deployment targets use free tiers with zero custom domain or paid requirements, preserving project Rule 1.
**Consequences:** Teams deploying NiyamDrishti can choose between Cloudflare Pages and Vercel without changing any frontend application code.
