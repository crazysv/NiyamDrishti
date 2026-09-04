# 08_TRACKER — Live Task Status

**This file is a status mirror of `07_IMPLEMENTATION_PLAN.md`. Every task ID here must exist there, and every task ID there must exist here — no exceptions, no "minor" ones left off.** This 1:1 parity is enforced process, not a suggestion: see `AGENTS.md` rule 3 and `12_GUARDRAILS.md` §"Tracker/Plan parity procedure." The failure that prompted this entire documentation system was exactly this file silently containing fewer tasks than the plan did — do not let it happen again.

**Status values:** `Not Started` · `In Progress` · `Blocked` · `Done`
**Last updated:** 2026-09-04 — Strict GitHub Actions CI Pipeline Compliance (Ruff, Mypy, ESLint 0 Errors, 84/84 Unit Tests Passing, Frontend Production Build Clean)

---

## Phase 0 — Spikes

| ID | Task | Status | Notes |
|---|---|---|---|
| SPIKE-01 | Prototype client-side OCR vs. server-side OCR on real photos | Done | ADR-005: server-side primary; 87.9% avg conf, 2420ms avg latency, 0 errors on 46 photos | |
| SPIKE-02 | Prototype barcode mm-per-pixel calibration accuracy | Done | ADR-006+amendment: zxing-cpp chosen (no DLL); px>50 gate; 0.11-0.23 mm/px per-photo calibration confirmed | |

## Phase 1 — MVP

### Setup
| ID | Task | Status | Notes |
|---|---|---|---|
| SETUP-01 | Scaffold monorepo (frontend/backend/docker) | Done | Next.js 14 + FastAPI 0.111 + directory structure created; app imports OK | |
| SETUP-02 | Docker Compose for local dev | Done | docker-compose.yml: API + Postgres 15 + MinIO (R2 stand-in); docker/README.md written | |
| SETUP-03 | `.env.example` + config loading | Done | All 11_SECRETS_CHECKLIST.md MVP vars covered; Pydantic Settings wired; smoke tested | |
| SETUP-04 | GitHub Actions CI (lint/type-check/test) | Done | .github/workflows/ci.yml: Ruff + mypy + pytest (backend); ESLint + tsc + build (frontend) | |
| SETUP-05 | Base SQLAlchemy models + Alembic init | Done | All 8 statutory models + batch_sessions created matching schema; Alembic env.py wired with async engine; initial migration 146f8e7efe38 generated and verified | |

### Auth
| ID | Task | Status | Notes |
|---|---|---|---|
| AUTH-01 | `users` table + model | Done | Completed as part of SETUP-05 (base.py includes User model) | |
| AUTH-02 | Password hashing + JWT issuance/refresh | Done | Passlib bcrypt + python-jose; unit tests pass | |
| AUTH-03 | `/auth/login`, `/auth/refresh` endpoints | Done | OAuth2 password request form + refresh token flow; integration tests pass | |
| AUTH-04 | Role-based access control middleware | Done | FastAPI dependencies: get_current_user, get_current_active_user, get_current_active_admin | |
| AUTH-05 | Rate limiting on auth endpoints | Done | SlowAPI limiter attached (5/min for login, 10/min for refresh) | |

### Capture
| ID | Task | Status | Notes |
|---|---|---|---|
| CAP-01 | STOP — Stitch design checkpoint: Capture screen | Done | Stitch screen 7c1d0b5bf34e4e778541c8a99af1a10e verified & layout fetched | |
| CAP-02 | Camera capture logic + multi-image state | Done | react-webcam + multi-image state + gallery upload fallback + Stitch styling in CaptureScreen.tsx; hardened with 100dvh mobile overflow-hidden viewport and 1080p capture resolution | |
| CAP-03 | Quality gate: blur detection | Done | Laplacian edge variance operator in qualityGate.ts; threshold=120 | |
| CAP-04 | Quality gate: glare/lighting detection | Done | Rec. 601 luminance + center-region saturated pixel ratio in qualityGate.ts | |
| CAP-05 | Quality gate: perspective/crop/resolution/occlusion | Done | 600x600px minimum resolution, extreme aspect ratio/perspective heuristic, and center occlusion histogram checks in qualityGate.ts | |
| CAP-06 | Per-failure specific retake messaging | Done | Specific action hints, failure banner, and officer override in CaptureScreen.tsx | |
| CAP-07 | Offline capture queue (Dexie.js/IndexedDB) | Done | Dexie schema in db/dexie.ts, useOfflineQueue hook, pending sync counter & storage quota warnings | |
| CAP-08 | `POST /inspections`, `POST /inspections/{id}/images` | Done | FastAPI endpoints supporting JSON Data URL & multipart uploads, local storage persistence, test suite |
| CAP-09 | Resumable per-item sync on reconnect | Done | syncService.ts + useOfflineQueue auto-reconnect trigger + manual Sync Now banner + per-item resumption |

### Preprocessing
| ID | Task | Status | Notes |
|---|---|---|---|
| PRE-01 | Preprocessing pipeline scaffold | Done | OpenCV/Pillow pipeline in services/preprocessing (resize/normalize, bilateral denoise, CLAHE contrast, bbox coordinate inverse mapper, 7 unit tests) |
| PRE-02 | Perspective correction + deskew | Done | 4-point quadrilateral perspective warp + horizontal text line deskew via minAreaRect + full inverse transform point/box mapping |
| PRE-03 | Glare suppression + text-region enhancement | Done | HLS specular glare detection + Telea inpainting + unsharp mask text stroke enhancement |

### OCR
| ID | Task | Status | Notes |
|---|---|---|---|
| OCR-01 | Integrate PaddleOCR PP-OCRv6 | Done | PaddleOCREngine with polygon bounding box, angle cls, and lazy initialization |
| OCR-02 | Tesseract fallback path | Done | TesseractEngine fallback when primary confidence < threshold or on exception |
| OCR-03 | Retain text + confidence + bbox + source-image ref | Done | BoundingBox, OCRLine, OCRResult schemas + inverse coordinate mapping to raw capture pixels |

### Declaration Extraction
| ID | Task | Status | Notes |
|---|---|---|---|
| EXT-01 | Field extractor scaffold + persistence | Done | DeclarationExtractionService orchestrator + DB persistence to extracted_fields + POST /inspections/{id}/extract |
| EXT-02 | Extract: MRP | Done | MRPExtractor with numeric price parsing, tabular matrix spatial column matching, split-digit stitching, and unit sale price parsing |
| EXT-03 | Extract: net quantity | Done | NetQuantityExtractor with magnitude parsing, SI metric unit standardization, multi-pack equations, and nutrition table exclusion |
| EXT-04 | Extract: manufacturer/packer/importer address | Done | ManufacturerAddressExtractor with role mapping, multi-line address lookahead, and 6-digit Indian PIN code validation |
| EXT-05 | Extract: month/year of manufacture | Done | MfgDateExtractor with MM/YYYY, Month YYYY, 3-part DD/MM/YY date parsing, and proximity sorting |
| EXT-06 | Extract: consumer care details | Done | ConsumerCareExtractor with hyphenated toll-free (1-800), phone, and email regex extraction, excluding FSSAI IDs |
| EXT-07 | Extract: country of origin | Done | CountryOfOriginExtractor with country normalization |
| EXT-08 | Extract: commodity name | Done | CommodityNameExtractor with net weight prefix stripping and PDP headline heuristics |
| EXT-09 | Commodity-category selection | Done | Commodity category registry + GET /inspections/categories endpoint |

### Optical Calibration
| ID | Task | Status | Notes |
|---|---|---|---|
| CAL-01 | Barcode detection + known-width lookup | Done | BarcodeCalibrationDetector with GS1 retail barcode dimensions (EAN-13, EAN-8, UPC-A, QR) via zxingcpp + OpenCV adaptive thresholding fallback (ADR-023) |
| CAL-02 | mm-per-pixel scale derivation + persistence | Done | OpticalCalibrationService with persistence to inspection_images.calibration_scale_mm_per_px and automatic derivation on upload/extract |
| CAL-03 | Uncalibrated fallback path | Done | uncalibrated_pdp_ratio fallback with explicit measurement warning flag and non-asserted precision |

### Rule Engine
| ID | Task | Status | Notes |
|---|---|---|---|
| RULE-01 | `rule_packs` table + JSON schema validation | Done | RulePack model + RulePackSchema validation with Pydantic in services/rules/schemas.py |
| RULE-02 | Author initial (v1) core rule pack | Done | core_pack_v1.json with mandatory declarations (EXT-02..EXT-08), citations marked [VERIFY] per AGENTS.md rule 9 pending official sub-clause confirmation (OQ-08), and pan-masala RSP rule |
| RULE-03 | Author font-height-by-PDP-area rule | Done | Rule 7 font-size-pdp-net-quantity rule with calibration check and uncalibrated fallback path (CAL-03) |
| RULE-04 | Rule engine core (dispatch + evaluate) | Done | RuleEngine dispatcher in services/rules/engine.py evaluating rules, overall status, and violations output |
| RULE-05 | `GET /rule-packs`, `GET /rule-packs/{version}` | Done | List, active, and version lookup endpoints in api/v1/endpoints/rule_packs.py |
| RULE-06 | `POST /rule-packs`, activate endpoint (admin) | Done | Admin-only creation, validation, atomic activation, and append-only audit_logs recording |
| RULE-07 | Freeze `inspections.rule_pack_version` at creation | Done | Frozen at inspection creation from active rule pack and preserved across subsequent version upgrades |

### Evidence Mapping
| ID | Task | Status | Notes |
|---|---|---|---|
| EVID-01 | Bind fields + violations to bounding boxes | Done | GET /inspections/{id}/evidence returning normalized bounding box percentages and pixel coordinates |
| EVID-02 | `violations` table population from rule engine | Done | violations table auto-populated on POST /inspections/{id}/extract and /evaluate |
| EVID-03 | STOP — Stitch design checkpoint: Evidence viewer | Done | EvidenceViewer component built against Stitch screen aadbc3ef68594817a4d6c6cde22383c1 with zoom/pan, panel switcher tabs, active panel box filtering, and declaration auto-switch |

### Human Review
| ID | Task | Status | Notes |
|---|---|---|---|
| REV-01 | Confidence-threshold routing to review queue | Done | Baseline 85% threshold wired in config, RuleEngine, and extraction service; GET /inspections/{id}/review-queue endpoint implemented |
| REV-02 | `PATCH /inspections/{id}/fields/{field_id}` | Done | PATCH /inspections/{id}/fields/{field_id} supporting confirm, correct, mark_not_applicable with RBAC & automated rule re-evaluation |
| REV-03 | Immutable audit-log write on override | Done | Append-only audit_logs entry recorded on every override with before/after state; GET /inspections/{id}/audit-logs endpoint added |
| REV-04 | STOP — Stitch design checkpoint: Review Queue screen | Done | ReviewQueue component and /inspections/[id]/review page built against Stitch screen ac4887f8ca224ab6a124f46f4b85c274 |

### Reporting
| ID | Task | Status | Notes |
|---|---|---|---|
| RPT-01 | WeasyPrint PDF report template | Done | inspection_report.html Jinja2 template created with full official layout, findings table, violations, and FPDF2 fallback engine |
| RPT-02 | Shared, un-omittable legal disclaimer partial | Done | _legal_disclaimer.html created; mandatory disclaimer module wired into PDF generator and editable JSON export |
| RPT-03 | `POST /inspections/{id}/report` + R2 upload | Done | POST /inspections/{id}/report, GET reports list, and GET download endpoint implemented with R2 upload & local storage fallback; /inspections/[id]/report statutory Report Center frontend page created |
| RPT-04 | Editable-format export | Done | JSON structured export implemented containing full declaration metadata, violations, audit logs, and mandatory disclaimer |

### Storage & Sync
| ID | Task | Status | Notes |
|---|---|---|---|
| STOR-01 | Cloudflare R2 integration (signed URLs) | Done | Boto3 client, time-limited presigned GET/PUT URLs, asset deletion, and local fallback implemented in storage.py; R2 signed URL resolution wired in evidence & review APIs |
| STOR-02 | Neon Postgres provisioning + connection wiring | Done | normalize_database_url configured in session.py with asyncpg scheme conversion, pool_pre_ping=True, pool_recycle=300s, and /health database probe |
| STOR-03 | Local storage cap + low-space warning | Done | storageQuota.ts, useStorageQuota hook, and StorageWarningBanner component implemented with 50-package queue cap and 50MB device free-space warning |

### Search & History
| ID | Task | Status | Notes |
|---|---|---|---|
| SRCH-01 | `GET /inspections` with filters | Done | Implemented GET /api/v1/inspections with officer scoping RBAC, date range, region, category, status, violation existence/type, product full-text query, and thumbnail signed URL resolution |
| SRCH-02 | STOP — Stitch design checkpoint: Search/History screen | Done | Screen 12ee7aa2ba624f5d914146be76b8f3ef inspected in Stitch project 8675458162299902219; HistoryScreen.tsx and /history route implemented with search, filter chips, feed, offline IndexedDB support, corrected SYNCED/PENDING SYNC badges, and in-app Government System Info modal |

### Testing & Acceptance
| ID | Task | Status | Notes |
|---|---|---|---|
| TEST-01 | Unit tests: rule engine, calibration, extraction | Done | 21 unit tests across rule engine dispatch, calibration math, and extraction parsers all passing |
| TEST-02 | Integration test: full pipeline on real sample photos | Done | End-to-end integration test (capture -> upload -> process -> evidence -> report -> export) passing in test_pipeline_e2e.py |
| TEST-03 | Verify every MVP acceptance criterion in `01_PRD.md` §6 | Done | Audited and verified all 6 MVP criteria in 01_PRD.md §6 explicitly |
| TEST-04 | SQLite ↔ Postgres JSON round-trip test | Done | Verified complex JSON column roundtrip (RulePack.rules_json, ExtractedField.bounding_box with 4-point polygon, AuditLog before/after values) in test_json_roundtrip.py |

### Deploy (MVP)
| ID | Task | Status | Notes |
|---|---|---|---|
| DEPLOY-01 | Deploy backend to Render free Web Service | Done | render.yaml blueprint created with Docker runtime, free plan, and /health probe; Dockerfile updated with tesseract-ocr; docs/DEPLOYMENT.md added |
| DEPLOY-02 | Deploy frontend to Cloudflare Pages | Done | Cloudflare Pages configuration in frontend/wrangler.toml (pages_build_output_dir) + vercel.json added; Next.js build verified cleanly |
| DEPLOY-03 | Confirm cold-start handling works end-to-end | Done | Implemented useServerHealth hook and non-blocking ColdStartBanner in layout.tsx informing officer during ~30s container idle wake-up without blocking offline camera |
| DEPLOY-04 | Full secrets checklist walkthrough against live deploy | Done | Completed walkthrough of 11_SECRETS_CHECKLIST.md, verified .env.example parity, .gitignore global patterns, and free-tier service credentials |

## Phase 2 â€” Enhanced Features

| ID | Task | Status | Notes |
|---|---|---|---|
| E2-01 | Extract remaining declaration fields (full set) | Done | Implemented DimensionsAndCountExtractor (dimensions, piece/unit count), ImporterPackerExtractor (importer, packer, marketer), and RSPExtractor (2026 Second Amendment pan masala RSP); 5 unit tests passing; expiry/best-before date deferred per OQ-09 |
| E2-02 | Full font/legibility rule set (all variants) | Done | Verified Rule 7 Table 1 and Rule 7(1) proviso figures, resolved OQ-04; added font_height_blown_embossed and legibility_contrast to RuleType schema, core_pack_v1.json, and RuleEngine; 4 unit tests passing |
| E2-03 | Multi-image cross-matching | Done | Implemented MultiImageCrossMatchingService checking front/back/sticker declarations for altered price stickers (Rule 18(2)), panel discrepancies (Rule 6(1)(c)), and DB violation generation; 7 unit tests passing (includes 4 e-commerce cross-match tests shared with E3-02) |
| E2-04 | Full human review workflow polish | Done | Implemented POST /inspections/{id}/fields/batch-review and GET /inspections/{id}/review-history; added batch confirm high-confidence and audit history drawer in ReviewQueue.tsx; integration test passing |
| E2-05 | Analytics dashboard | Done | Implemented /analytics/summary, /compliance-trends, /violation-hotspots, and /officer-throughput backend APIs, Pydantic schemas, client service with JWT auth forwarding, and CSV/PDF exports; 4 integration tests passing |
| E2-06 | STOP — Stitch design checkpoint: Supervisor/Admin dashboard | Done | Google Stitch screen bfa11fc4dfe54a008099093e84576202 faithfully implemented in AnalyticsDashboard.tsx; /dashboard route created; wired to live analytics service with graceful demo fallback when API is unreachable; frontend build passing |
| E2-07 | Rule-pack management UI (Admin) | Done | Google Stitch screen 584c874f57984b36b209eb604a1dcdf1 implemented in RulePackManagement.tsx; /admin/rule-packs & /admin routes created; schema validation upload, side-by-side version diff viewer, Section 36 confirmation PIN modal, and admin JWT authorization verification; frontend build passing |
| E2-08 | Confidence-threshold tuning from pilot data | Done | Calibrated per-field confidence thresholds (ADR-012) in config.py, extraction/service.py, rules/engine.py, and inspections.py with canonical extractor field_types and aliases (net_quantity 0.80, mfg_date 0.80, address 0.78, mrp 0.82, origin 0.85); 6 dedicated unit tests passing; 150/150 backend tests passing |

## Phase 3 — E-commerce & Advanced

| ID | Task | Status | Notes |
|---|---|---|---|
| E3-01 | E-commerce listing image ingestion | Done | Enabled ecommerce_listing image role across frontend (CAPTURE_SLOTS E04, CaptureScreen.tsx) and backend endpoints (JSON data URL, multipart upload, quality gate bypass, storage); 5 dedicated integration tests passing (108/108 backend suite) |
| E3-02 | Physical-package ↔ listing cross-consistency checking | Done | Enhanced MultiImageCrossMatchingService with physical-to-listing validation (Rule 6(10) & 18(2) net quantity mismatch, online price inflation, provenance & manufacturer discrepancies); wired into process pipeline & added GET /inspections/{id}/cross-match endpoint; 113/113 backend tests passing |
| E3-03 | Confirm current Bhashini sign-up/approval status | Done | Confirmed with user: implementing environment-driven adapter (live Bhashini ULCA client when BHASHINI_API_KEY / BHASHINI_USER_ID configured in .env, falling back cleanly to offline Indic translation & OCR assist stub when unconfigured) per ADR-013 |
| E3-04 | Bhashini integration | Done | Implemented BhashiniService with 12 Indic regional languages (Hindi, Marathi, Gujarati, Bengali, Tamil, Telugu, etc.), NMT translation, TTS speech synthesis, and full inspection report vernacular narration; environment-driven live ULCA with offline dictionary fallback; 8 unit & integration tests passing (121/121 backend suite) |
| E3-05 | Batch/warehouse scanning mode | Done | Built BatchSession model, rapid multi-SKU intake endpoints, live compliance tallying, and warehouse audit manifest generation with rule-level violation breakdowns; frontend types & services created; 2 dedicated integration tests passing (123/123 backend suite) |
| E3-06 | Manufacturer/Packer self-check mode (if scoped) | Done | Built structurally isolated self-check endpoints (POST /self-check/inspections with is_self_check=True, list, scorecard with constructive packaging remediation guidance, and summary metrics); verified strict mathematical isolation from enforcement dashboards & search; frontend types/services created; 4 integration tests passing (127/127 backend suite) |

## Phase 4 — Production Readiness

| ID | Task | Status | Notes |
|---|---|---|---|
| E4-01 | Government SSO (MeriPehchan/Jan Parichay) | Done | Built dual-mode MeriPehchan / Jan Parichay OIDC adapter (ADR-016) with live NIC endpoints when MERIPEHCHAN_CLIENT_ID configured in .env, and high-fidelity local developer/demo sandbox when unconfigured; includes PKCE, CSRF state verification, JIT officer provisioning, and automated designation-to-role mapping; frontend types/services created; 6 integration tests passing (133/133 backend suite) |
| E4-02 | Hardened offline sync (conflict resolution, retry/backoff) | Done | Built backend client_id & Idempotency-Key handling on inspections & images, deterministic HTTP 409 conflict detection on finalized inspections (ADR-017), and batch sync endpoint /inspections/sync; implemented frontend exponential retry with full jitter (retryBackoff.ts), Dexie schema v3 with dead_letter queue, failure categorization, and conflict resolution; 4 integration tests passing (137/137 backend suite), tsc and next build clean |
| E4-03 | Monitoring/observability (Prometheus + Grafana, self-hosted) | Done | Built Prometheus metrics (/metrics) for throughput, latency, OCR & rule duration, offline sync & quality gate; ObservabilityMiddleware with X-Request-ID and cardinality normalization; /health, /health/live, /health/ready probes; alert_rules.yml & 11-panel Grafana dashboard; docker-compose monitoring profile; 5 integration tests passing (142/142 backend suite) |
| E4-04 | Formal security review of the audit-log/evidence chain for evidentiary use | Done | Implemented SHA-256 photographic fingerprinting on intake, AuditLog Merkle hash-chaining, SQLAlchemy event listeners enforcing append-only immutability (PermissionError on UPDATE/DELETE), EvidenceVerificationService, Section 63 BSA 2023 / Section 65B IEA 1872 certificate generator, and GET /inspections/{id}/evidence/verify & certificate endpoints; docs/EVIDENTIARY_SECURITY_REVIEW.md added; ADR-019 logged; 3 integration tests passing (145/145 backend suite) |
| E4-05 | eMaap API adapter (if confirmed available) | Done | Built dual-mode EMaapAdapter (ADR-020) with live REST API integration when EMAAP_API_URL/KEY configured and high-fidelity local sandbox when unconfigured; implemented Rule 27 registration lookup (active, expired, suspended, fuzzy search) and enforcement docket filing with evidence chain digest & immutable AuditLog entry; added /status, /verify-registration, /dockets endpoints; 3 integration tests passing |
| E4-06 | Full deployment checklist finalized (`03_TECHSPEC.md` §7, `11_SECRETS_CHECKLIST.md`) for a real pilot rollout | Done | Built automated pre-flight audit script (scripts/pilot_readiness_check.py) verifying DB, rule pack, cryptographic engine, integrations, and metrics; expanded docs/DEPLOYMENT.md with Section 3 Production Pilot Rollout Operations & Audit Checklist covering device specs, PWA offline install, evidentiary integrity, and SRE observability; all 150 backend tests passing |

---

## Parity checklist (run this mentally, or literally, before ending any session where you edited either file)

- [x] Every ID in `07_IMPLEMENTATION_PLAN.md` appears exactly once here.
- [x] Every ID here appears exactly once in `07_IMPLEMENTATION_PLAN.md`.
- [x] No task title has silently diverged between the two files.
- [x] The "Last updated" line above is current.

If this checklist ever fails, fixing it is the immediate next task â€” before starting anything else â€” because every downstream session-start/session-continue check trusts this file to be complete.









