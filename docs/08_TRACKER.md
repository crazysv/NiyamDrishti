# 08_TRACKER â€” Live Task Status

**This file is a status mirror of `07_IMPLEMENTATION_PLAN.md`. Every task ID here must exist there, and every task ID there must exist here â€” no exceptions, no "minor" ones left off.** This 1:1 parity is enforced process, not a suggestion: see `AGENTS.md` rule 3 and `12_GUARDRAILS.md` Â§"Tracker/Plan parity procedure." The failure that prompted this entire documentation system was exactly this file silently containing fewer tasks than the plan did â€” do not let it happen again.

**Status values:** `Not Started` · `In Progress` · `Blocked` · `Done`
**Last updated:** 2026-09-03 — E2-03 Done (Multi-Image Cross-Matching Complete; 95/95 Tests Passing)

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
| SETUP-05 | Base SQLAlchemy models + Alembic init | Done | All 8 tables created matching 06_SCHEMA.md; Alembic env.py wired; create_all verified on SQLite | |

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
| CAP-02 | Camera capture logic + multi-image state | Done | react-webcam + multi-image state + gallery upload fallback + Stitch styling in CaptureScreen.tsx | |
| CAP-03 | Quality gate: blur detection | Done | Laplacian edge variance operator in qualityGate.ts; threshold=120 | |
| CAP-04 | Quality gate: glare/lighting detection | Done | Rec. 601 luminance + center-region saturated pixel ratio in qualityGate.ts | |
| CAP-05 | Quality gate: perspective/crop/resolution/occlusion | Done | 600x600px minimum resolution and frame boundary checks | |
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
| EXT-02 | Extract: MRP | Done | MRPExtractor with numeric price parsing, INR currency, and inclusive of all taxes verification |
| EXT-03 | Extract: net quantity | Done | NetQuantityExtractor with magnitude parsing and SI metric unit standardization (g, kg, ml, l, pieces) |
| EXT-04 | Extract: manufacturer/packer/importer address | Done | ManufacturerAddressExtractor with role mapping, multi-line address lookahead, and 6-digit Indian PIN code validation |
| EXT-05 | Extract: month/year of manufacture | Done | MfgDateExtractor with MM/YYYY and Month YYYY date parsing and normalization |
| EXT-06 | Extract: consumer care details | Done | ConsumerCareExtractor with toll-free, phone, and email regex extraction |
| EXT-07 | Extract: country of origin | Done | CountryOfOriginExtractor with country normalization |
| EXT-08 | Extract: commodity name | Done | CommodityNameExtractor with explicit declaration headers and prominent headline heuristics |
| EXT-09 | Commodity-category selection | Done | Commodity category registry + GET /inspections/categories endpoint |

### Optical Calibration
| ID | Task | Status | Notes |
|---|---|---|---|
| CAL-01 | Barcode detection + known-width lookup | Done | BarcodeCalibrationDetector with GS1 retail barcode dimensions (EAN-13, EAN-8, UPC-A) via OpenCV + pyzbar fallback |
| CAL-02 | mm-per-pixel scale derivation + persistence | Done | OpticalCalibrationService with persistence to inspection_images.calibration_scale_mm_per_px and automatic derivation on upload/extract |
| CAL-03 | Uncalibrated fallback path | Done | uncalibrated_pdp_ratio fallback with explicit measurement warning flag and non-asserted precision |

### Rule Engine
| ID | Task | Status | Notes |
|---|---|---|---|
| RULE-01 | `rule_packs` table + JSON schema validation | Done | RulePack model + RulePackSchema validation with Pydantic in services/rules/schemas.py |
| RULE-02 | Author initial (v1) core rule pack | Done | core_pack_v1.json with mandatory declarations (EXT-02..EXT-08), verified citations, and pan-masala RSP rule |
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
| EVID-03 | STOP — Stitch design checkpoint: Evidence viewer | Done | EvidenceViewer component built against Stitch screen aadbc3ef68594817a4d6c6cde22383c1 with zoom/pan and sync |

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
| RPT-03 | `POST /inspections/{id}/report` + R2 upload | Done | POST /inspections/{id}/report, GET reports list, and GET download endpoint implemented with R2 upload & local storage fallback |
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
| SRCH-02 | STOP — Stitch design checkpoint: Search/History screen | Done | Screen 12ee7aa2ba624f5d914146be76b8f3ef inspected in Stitch project 8675458162299902219; HistoryScreen.tsx and /history route implemented matching design with search, filter chips, feed, and offline IndexedDB support |

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
| DEPLOY-02 | Deploy frontend to Cloudflare Pages | Done | Cloudflare Pages configuration added in frontend/wrangler.toml; Next.js Turbopack build verified cleanly |
| DEPLOY-03 | Confirm cold-start handling works end-to-end | Done | Implemented useServerHealth hook and non-blocking ColdStartBanner in layout.tsx informing officer during ~30s container idle wake-up without blocking offline camera |
| DEPLOY-04 | Full secrets checklist walkthrough against live deploy | Done | Completed walkthrough of 11_SECRETS_CHECKLIST.md, verified .env.example parity, .gitignore global patterns, and free-tier service credentials |

## Phase 2 â€” Enhanced Features

| ID | Task | Status | Notes |
|---|---|---|---|
| E2-01 | Extract remaining declaration fields (full set) | Done | Implemented DimensionsAndCountExtractor (dimensions, piece/unit count), ImporterPackerExtractor (importer, packer, marketer), and RSPExtractor (2026 Second Amendment pan masala RSP); 5 unit tests passing |
| E2-02 | Full font/legibility rule set (all variants) | Done | Verified Rule 7 Table 1 and Rule 7(1) proviso figures, resolved OQ-04; added font_height_blown_embossed and legibility_contrast to RuleType schema, core_pack_v1.json, and RuleEngine; 4 unit tests passing |
| E2-03 | Multi-image cross-matching | Done | Implemented MultiImageCrossMatchingService checking front/back/sticker declarations for altered price stickers (Rule 18(2)), panel discrepancies (Rule 6(1)(c)), and DB violation generation; 3 unit tests passing |
| E2-04 | Full human review workflow polish | Done | Implemented POST /inspections/{id}/fields/batch-review and GET /inspections/{id}/review-history; added batch confirm high-confidence and audit history drawer in ReviewQueue.tsx; integration test passing |
| E2-05 | Analytics dashboard | Done | Implemented /analytics/summary, /compliance-trends, /violation-hotspots, and /officer-throughput backend APIs, Pydantic schemas, and client service; 4 integration tests passing (100/100 backend suite) |
| E2-06 | STOP â€” Stitch design checkpoint: Supervisor/Admin dashboard | Not Started | |
| E2-07 | Rule-pack management UI (Admin) | Not Started | |
| E2-08 | Confidence-threshold tuning from pilot data | Not Started | |

## Phase 3 â€” E-commerce & Advanced

| ID | Task | Status | Notes |
|---|---|---|---|
| E3-01 | E-commerce listing image ingestion | Not Started | |
| E3-02 | Physical-package â†” listing cross-consistency checking | Not Started | |
| E3-03 | Confirm current Bhashini sign-up/approval status | Not Started | |
| E3-04 | Bhashini integration | Not Started | |
| E3-05 | Batch/warehouse scanning mode | Not Started | |
| E3-06 | Manufacturer/Packer self-check mode (if scoped) | Not Started | |

## Phase 4 â€” Production Readiness

| ID | Task | Status | Notes |
|---|---|---|---|
| E4-01 | Government SSO (MeriPehchan/Jan Parichay) | Not Started | |
| E4-02 | Hardened offline sync (conflict resolution, retry/backoff) | Not Started | |
| E4-03 | Monitoring/observability | Not Started | |
| E4-04 | Security review of audit-log/evidence chain | Not Started | |
| E4-05 | eMaap API adapter (if confirmed available) | Not Started | |
| E4-06 | Full deployment checklist for real pilot rollout | Not Started | |

---

## Parity checklist (run this mentally, or literally, before ending any session where you edited either file)

- [x] Every ID in `07_IMPLEMENTATION_PLAN.md` appears exactly once here.
- [x] Every ID here appears exactly once in `07_IMPLEMENTATION_PLAN.md`.
- [x] No task title has silently diverged between the two files.
- [x] The "Last updated" line above is current.

If this checklist ever fails, fixing it is the immediate next task â€” before starting anything else â€” because every downstream session-start/session-continue check trusts this file to be complete.









