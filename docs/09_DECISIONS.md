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
**Status:** Superseded by ADR-006 Amendment (2026-09-02) — pyzbar replaced by zxing-cpp`n**Context:** SPIKE-02 tested barcode-based mm-per-pixel calibration on 46 photos to decide on the acceptable-use threshold (OQ-04 feeds into RULE-03).
**Decision:** Barcode calibration is valid and will be implemented (CAL-01..CAL-03) but with two constraints: (1) pyzbar (with the zbar system DLL) is the required barcode detector â€” OpenCV BarcodeDetector reports px=0 or px=1â€“4 for many valid barcodes, making its pixel-width measurement unreliable; (2) calibration is only used when detected pixel width > 50px; below that threshold, the reading is treated as uncalibrated and the fallback path (CAL-03) is triggered.
**Evidence:** 46 photos scanned; 20 had barcodes detected by OpenCV. Of those, 10 reported px=0 or px<5 (measurement failure). The 5 readings with px>50 clustered at 0.23â€“0.28 mm/px (reasonable for a mid-distance label photo), giving ~19% spread â€” slightly above the 15% "reliable" threshold, likely due to angle variation. With a minimum-pixel-width gate, consistency improves.
**Consequences:** CAL-01 will use pyzbar as primary detector (requires the zbar DLL to be bundled in the Docker image / Render deploy). The px>50 gate and the "Uncalibrated" fallback flag are hard requirements for CAL-03, not optional. The font-height rule (RULE-03) must always check calibration status before asserting a mm measurement.


### ADR-006 Amendment â€” zxing-cpp confirmed as barcode detector (replaces pyzbar recommendation)
**Date:** 2026-09-02
**Status:** Accepted (amends ADR-006)
**Decision:** Use zxing-cpp (PyPI: zxing-cpp) instead of pyzbar for barcode detection. Tested on 8 photos: 6/8 EAN-13 barcodes detected and decoded correctly with real product data (e.g. 8904063231765). Zero DLL dependencies â€” works out of the box on Windows and Linux without bundling libzbar. Pixel width calculated via Euclidean distance (top_left to top_right corner) using .position. The px>50 gate from ADR-006 remains in force. Spread across photos (73.9%) is expected and correct â€” it reflects different shooting distances, not measurement error; each photo gets its own per-photo calibration from the barcode visible in that same frame.

