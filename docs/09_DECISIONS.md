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
