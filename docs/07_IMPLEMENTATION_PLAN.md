# 07_IMPLEMENTATION_PLAN — Granular Build Plan

**This is the ground truth of "what to build, in what order."** Every task below has a stable ID. `08_TRACKER.md` mirrors this list **exactly** — same IDs, same task titles, same total count — and only adds a status column. If you add, split, merge, or remove a task here, you make the identical edit in `08_TRACKER.md` in the same turn. This 1:1 parity is the specific fix for the failure that happened last time (see `AGENTS.md` rule 3). Do not let these two files diverge, even temporarily.

Each task lists: what it is, what it depends on, which docs govern it, and what "done" means. "Done" is the bar — don't mark a task complete in the tracker until its Done-when condition is actually true.

---

## Phase 0 — Spikes

| ID | Task | Depends on | Docs | Done when |
|---|---|---|---|---|
| SPIKE-01 | Prototype client-side OCR (PaddleOCR.js or Tesseract.js WASM) against 10–20 real label photos on a real mid-range Android phone; measure accuracy and latency | — | `MASTER_CONTENT.md` §11.3 | Written comparison exists; a decision is logged in `09_DECISIONS.md` (client-side, server-side, or hybrid) |
| SPIKE-02 | Prototype barcode-width mm-per-pixel calibration against 10–20 real photos at varied angles/distances; measure error margin | — | `MASTER_CONTENT.md` §9.4 | Error margin documented; a decision on acceptable-use threshold logged in `09_DECISIONS.md` |

## Phase 1 — MVP

### Setup
| ID | Task | Depends on | Docs |
|---|---|---|---|
| SETUP-01 | Scaffold monorepo: `/frontend` (Next.js), `/backend` (FastAPI), `/docker` | — | `03_TECHSPEC.md` §1 |
| SETUP-02 | Docker Compose for local dev (API + local Postgres/SQLite switch + local file-storage stand-in for R2) | SETUP-01 | `03_TECHSPEC.md` §7 |
| SETUP-03 | `.env.example` covering every var in `11_SECRETS_CHECKLIST.md`; wire config loading (Pydantic Settings) | SETUP-01 | `11_SECRETS_CHECKLIST.md` |
| SETUP-04 | GitHub Actions: lint (Ruff) + type-check (mypy) + test (pytest) on push | SETUP-01 | `03_TECHSPEC.md` §7 |
| SETUP-05 | Base SQLAlchemy models + Alembic init, matching `06_SCHEMA.md` exactly | SETUP-01 | `06_SCHEMA.md` |

### Auth
| ID | Task | Depends on | Docs |
|---|---|---|---|
| AUTH-01 | `users` table + model (`06_SCHEMA.md`) | SETUP-05 | `06_SCHEMA.md` |
| AUTH-02 | Password hashing (bcrypt) + JWT issuance/refresh | AUTH-01 | `03_TECHSPEC.md` §3 |
| AUTH-03 | `POST /auth/login`, `POST /auth/refresh` endpoints | AUTH-02 | `03_TECHSPEC.md` §3 |
| AUTH-04 | Role-based access control (officer/supervisor/admin) middleware | AUTH-02 | `01_PRD.md` §3 |
| AUTH-05 | Rate limiting on auth endpoints (slowapi) | AUTH-03 | `03_TECHSPEC.md` §5 |

### Capture (frontend logic — pixels come from Stitch, see `05_DESIGN.md`)
| ID | Task | Depends on | Docs |
|---|---|---|---|
| CAP-01 | **STOP — Stitch design checkpoint** for the Capture screen before building UI | SETUP-01 | `05_DESIGN.md` §1 |
| CAP-02 | Camera capture logic (react-webcam) + multi-image-per-inspection state | CAP-01 | `04_APPFLOW.md` §1 |
| CAP-03 | Client-side quality gate: blur detection | CAP-02 | `MASTER_CONTENT.md` §10.1 |
| CAP-04 | Client-side quality gate: glare / lighting detection | CAP-02 | `MASTER_CONTENT.md` §10.1 |
| CAP-05 | Client-side quality gate: perspective / crop / resolution / occlusion checks | CAP-02 | `MASTER_CONTENT.md` §10.1 |
| CAP-06 | Per-failure specific retake messaging (never a generic "bad photo") | CAP-03,CAP-04,CAP-05 | `01_PRD.md` US-02 |
| CAP-07 | Offline capture queue (Dexie.js/IndexedDB) with visible "pending sync" state | CAP-02 | `03_TECHSPEC.md` §5 |
| CAP-08 | `POST /inspections`, `POST /inspections/{id}/images` endpoints | AUTH-04 | `03_TECHSPEC.md` §3 |
| CAP-09 | Resumable, per-item sync of queued captures on reconnect | CAP-07,CAP-08 | `01_PRD.md` US-11 |

### Preprocessing
| ID | Task | Depends on | Docs |
|---|---|---|---|
| PRE-01 | Preprocessing pipeline scaffold (OpenCV + Pillow): resize, denoise, contrast | CAP-08 | `MASTER_CONTENT.md` §10.2 |
| PRE-02 | Perspective correction + deskew | PRE-01 | `MASTER_CONTENT.md` §10.2 |
| PRE-03 | Optional glare suppression + text-region enhancement | PRE-01 | `MASTER_CONTENT.md` §10.2 |

### OCR
| ID | Task | Depends on | Docs |
|---|---|---|---|
| OCR-01 | Integrate PaddleOCR PP-OCRv6 (tiny/small tier per SPIKE-01 outcome) | PRE-03,SPIKE-01 | `MASTER_CONTENT.md` §11.3 |
| OCR-02 | Tesseract fallback path when PaddleOCR confidence is globally low or unavailable | OCR-01 | `MASTER_CONTENT.md` §11.3 |
| OCR-03 | Ensure every OCR result retains text + confidence + bounding box + source-image reference (no path that discards these) | OCR-01 | `MASTER_CONTENT.md` §10.3 |

### Declaration Extraction
| ID | Task | Depends on | Docs |
|---|---|---|---|
| EXT-01 | Field extractor scaffold + `extracted_fields` persistence | OCR-03 | `06_SCHEMA.md` |
| EXT-02 | Extract: MRP | EXT-01 | `MASTER_CONTENT.md` §4.2 |
| EXT-03 | Extract: net quantity | EXT-01 | `MASTER_CONTENT.md` §4.2 |
| EXT-04 | Extract: manufacturer/packer/importer address | EXT-01 | `MASTER_CONTENT.md` §4.2 |
| EXT-05 | Extract: month/year of manufacture | EXT-01 | `MASTER_CONTENT.md` §4.2 |
| EXT-06 | Extract: consumer care details | EXT-01 | `MASTER_CONTENT.md` §4.2 |
| EXT-07 | Extract: country of origin | EXT-01 | `MASTER_CONTENT.md` §4.2 |
| EXT-08 | Extract: commodity name/common name | EXT-01 | `MASTER_CONTENT.md` §4.2 |
| EXT-09 | Commodity-category selection (manual, feeds category-specific rules e.g. pan masala) | EXT-01 | `04_APPFLOW.md` §6 |

### Optical Calibration
| ID | Task | Depends on | Docs |
|---|---|---|---|
| CAL-01 | Barcode detection (pyzbar) + known-width lookup (EAN-13 = 37.29mm nominal) | OCR-03,SPIKE-02 | `MASTER_CONTENT.md` §9.4 |
| CAL-02 | mm-per-pixel scale derivation + persistence on `inspection_images` | CAL-01 | `06_SCHEMA.md` |
| CAL-03 | "Uncalibrated" fallback path (relative PDP-ratio estimate, explicitly flagged) when no barcode is found | CAL-01 | `MASTER_CONTENT.md` §9.4 |

### Rule Engine
| ID | Task | Depends on | Docs |
|---|---|---|---|
| RULE-01 | `rule_packs` table + JSON schema validation on upload | SETUP-05 | `06_SCHEMA.md` §3 |
| RULE-02 | Author the initial (v1) core rule pack: declaration-presence rules for the fields in EXT-02..EXT-08 | RULE-01 | `06_SCHEMA.md` §3 |
| RULE-03 | Author the font-height-by-PDP-area rule (using CAL output) | RULE-01,CAL-02 | `MASTER_CONTENT.md` §4.3 |
| RULE-04 | Rule engine core: dispatch by rule `type`, evaluate against extracted fields → verdict | RULE-02,EXT-09 | `MASTER_CONTENT.md` §10.5 |
| RULE-05 | `GET /rule-packs`, `GET /rule-packs/{version}` endpoints | RULE-01 | `03_TECHSPEC.md` §3 |
| RULE-06 | `POST /rule-packs`, `POST /rule-packs/{version}/activate` (admin-only) endpoints | RULE-01,AUTH-04 | `03_TECHSPEC.md` §3 |
| RULE-07 | Confirm-and-freeze: `inspections.rule_pack_version` set at creation, never mutated afterward | RULE-04 | `06_SCHEMA.md` §2 (`inspections` invariant) |

### Evidence Mapping
| ID | Task | Depends on | Docs |
|---|---|---|---|
| EVID-01 | Bind every extracted field + every violation to its source bounding box(es) | EXT-01,RULE-04 | `MASTER_CONTENT.md` §10.6 |
| EVID-02 | `violations` table population from rule-engine output | RULE-04 | `06_SCHEMA.md` |
| EVID-03 | **STOP — Stitch design checkpoint** for the Evidence viewer (zoom/pan + highlighted box) before building UI | CAP-01 | `05_DESIGN.md` §1,§3 |

### Human Review
| ID | Task | Depends on | Docs |
|---|---|---|---|
| REV-01 | Confidence-threshold routing to review queue (baseline 85%, tune per Phase 1 testing) | EXT-01 | `MASTER_CONTENT.md` §10.8 |
| REV-02 | `PATCH /inspections/{id}/fields/{field_id}` (confirm/correct/mark-not-applicable) | REV-01,AUTH-04 | `03_TECHSPEC.md` §3 |
| REV-03 | Immutable `audit_logs` write on every override (no update/delete path ever touches this table) | REV-02 | `06_SCHEMA.md` §2 (`audit_logs`) |
| REV-04 | **STOP — Stitch design checkpoint** for the Review Queue screen before building UI | CAP-01 | `05_DESIGN.md` §1 |

### Reporting
| ID | Task | Depends on | Docs |
|---|---|---|---|
| RPT-01 | WeasyPrint HTML→PDF report template, including evidence thumbnails | EVID-01,RULE-02 | `MASTER_CONTENT.md` §10.9 |
| RPT-02 | Shared, un-omittable legal disclaimer partial included in every report variant | RPT-01 | `01_PRD.md` US-07 |
| RPT-03 | `POST /inspections/{id}/report` endpoint + R2 upload of the generated file | RPT-01 | `03_TECHSPEC.md` §3 |
| RPT-04 | Editable-format export (alongside PDF) | RPT-01 | `01_PRD.md` §4 (US-07) |

### Storage & Sync
| ID | Task | Depends on | Docs |
|---|---|---|---|
| STOR-01 | Cloudflare R2 integration (images, PDFs) with signed, time-limited URLs | SETUP-03 | `MASTER_CONTENT.md` §11.4 |
| STOR-02 | Neon Postgres provisioning + connection wiring (prod), SQLite path confirmed for local/offline | SETUP-05 | `03_TECHSPEC.md` §7 |
| STOR-03 | Local storage cap + warning before device runs out of space (offline queue) | CAP-07 | `MASTER_CONTENT.md` §14.1 |

### Search & History
| ID | Task | Depends on | Docs |
|---|---|---|---|
| SRCH-01 | `GET /inspections` with filters (officer, date range, region, violation type, product) | STOR-02 | `03_TECHSPEC.md` §3 |
| SRCH-02 | **STOP — Stitch design checkpoint** for the Search/History screen before building UI | CAP-01 | `05_DESIGN.md` §1 |

### Testing & Acceptance
| ID | Task | Depends on | Docs |
|---|---|---|---|
| TEST-01 | Unit tests: rule engine dispatch, calibration math, extraction parsers | RULE-04,CAL-02,EXT-09 | `03_TECHSPEC.md` §7 |
| TEST-02 | Integration test: full pipeline on a real sample photo set (capture → report) | RPT-03 | `01_PRD.md` §6 |
| TEST-03 | Verify every MVP acceptance criterion in `01_PRD.md` §6 explicitly, one by one | TEST-02 | `01_PRD.md` §6 |
| TEST-04 | SQLite ↔ Postgres round-trip test for `bounding_box`/`rules_json` JSON fields | STOR-02 | `06_SCHEMA.md` §4 |

### Deploy (MVP)
| ID | Task | Depends on | Docs |
|---|---|---|---|
| DEPLOY-01 | Deploy backend to Render free Web Service | STOR-01,STOR-02 | `MASTER_CONTENT.md` §11.14 |
| DEPLOY-02 | Deploy frontend to Cloudflare Pages | CAP-01..CAP-09 | `MASTER_CONTENT.md` §11.14 |
| DEPLOY-03 | Confirm cold-start behavior is handled gracefully in the client (per `03_TECHSPEC.md` §5) | DEPLOY-01,DEPLOY-02 | `03_TECHSPEC.md` §5 |
| DEPLOY-04 | Full `11_SECRETS_CHECKLIST.md` walkthrough against the live deployment | DEPLOY-01,DEPLOY-02 | `11_SECRETS_CHECKLIST.md` |

---

## Phase 2 — Enhanced Features

| ID | Task | Depends on | Docs |
|---|---|---|---|
| E2-01 | Extract remaining declaration fields not covered in Phase 1 (full set per `MASTER_CONTENT.md` §4.2) | EXT-01..EXT-09 | `MASTER_CONTENT.md` §4.2 |
| E2-02 | Full font/legibility rule set (all PDP thresholds + blown/formed/embossed/perforated variants — verify exact figures first, see OQ) | RULE-03 | `MASTER_CONTENT.md` §4.3 |
| E2-03 | Multi-image cross-matching (front/back/sticker declaration consistency) | EXT-01 | `MASTER_CONTENT.md` §9.3 |
| E2-04 | Full human review workflow polish (batch review, review history view) | REV-01..REV-04 | `MASTER_CONTENT.md` §10.8 |
| E2-05 | Analytics dashboard: compliance trends, violation hotspots, officer throughput | SRCH-01 | `MASTER_CONTENT.md` §10.11 |
| E2-06 | **STOP — Stitch design checkpoint** for the Supervisor/Admin dashboard | CAP-01 | `05_DESIGN.md` §1 |
| E2-07 | Rule-pack management UI (Admin) — upload, diff review, activate | RULE-06 | `04_APPFLOW.md` §4 |
| E2-08 | Confidence-threshold tuning based on real Phase 1 pilot data | REV-01 | `03_TECHSPEC.md` §4 |

## Phase 3 — E-commerce & Advanced

| ID | Task | Depends on | Docs |
|---|---|---|---|
| E3-01 | E-commerce listing image ingestion (`ecommerce_listing` image role) | STOR-01 | `06_SCHEMA.md` |
| E3-02 | Physical-package ↔ listing cross-consistency checking | E3-01,E2-03 | `MASTER_CONTENT.md` §10.12 |
| E3-03 | Confirm current Bhashini ULCA sign-up/approval status before starting integration | — | `MASTER_CONTENT.md` §11.11 |
| E3-04 | Bhashini integration: vernacular voice UI / Indic-language OCR assist | E3-03 | `MASTER_CONTENT.md` §5,§11.11 |
| E3-05 | Batch/warehouse scanning mode (many SKUs per session) | CAP-02 | `MASTER_CONTENT.md` §10.13 |
| E3-06 | (If scoped) Manufacturer/Packer self-check mode — structurally separate data path, never joined into enforcement dashboards | STOR-02 | `01_PRD.md` NG4, `06_SCHEMA.md` (`is_self_check`) |

## Phase 4 — Production Readiness

| ID | Task | Depends on | Docs |
|---|---|---|---|
| E4-01 | Government SSO (MeriPehchan/Jan Parichay) replacing self-rolled JWT auth | AUTH-01..AUTH-05 | `MASTER_CONTENT.md` §5 |
| E4-02 | Hardened offline sync: conflict resolution, retry/backoff | CAP-09 | `MASTER_CONTENT.md` §14.1 |
| E4-03 | Monitoring/observability (Prometheus + Grafana, self-hosted) | DEPLOY-01..DEPLOY-04 | `MASTER_CONTENT.md` §11.9 |
| E4-04 | Formal security review of the audit-log/evidence chain for evidentiary use | REV-03,EVID-01 | `MASTER_CONTENT.md` §14.2 |
| E4-05 | eMaap API adapter — only if a real, available integration point is confirmed | — | `MASTER_CONTENT.md` §5 |
| E4-06 | Full deployment checklist finalized (`03_TECHSPEC.md` §7, `11_SECRETS_CHECKLIST.md`) for a real pilot rollout | DEPLOY-01..DEPLOY-04 | `03_TECHSPEC.md` §7 |

---

## Notes for the agent

- Tasks marked **"STOP — Stitch design checkpoint"** are not optional gates — do not proceed to build the associated UI without either a Stitch export from the user or an explicit "go ahead without it for now" from the user, logged in `09_DECISIONS.md` if given.
- `Depends on` is a same-file task-ID reference; before starting a task, confirm its dependencies show `Done` in `08_TRACKER.md`.
- If you find a task is bigger than it looks once you're inside it, split it into sub-tasks with new IDs (e.g. `EXT-02a`, `EXT-02b`) — but do this in **both** this file and the tracker in the same turn, and note the split in `CHANGELOG.md`.
