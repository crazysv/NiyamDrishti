# 08_TRACKER â€” Live Task Status

**This file is a status mirror of `07_IMPLEMENTATION_PLAN.md`. Every task ID here must exist there, and every task ID there must exist here â€” no exceptions, no "minor" ones left off.** This 1:1 parity is enforced process, not a suggestion: see `AGENTS.md` rule 3 and `12_GUARDRAILS.md` Â§"Tracker/Plan parity procedure." The failure that prompted this entire documentation system was exactly this file silently containing fewer tasks than the plan did â€” do not let it happen again.

**Status values:** `Not Started` Â· `In Progress` Â· `Blocked` Â· `Done`
**Last updated:** 2026-09-02 — SETUP-01 through SETUP-05 all Done

---

## Phase 0 â€” Spikes

| ID | Task | Status | Notes |
|---|---|---|---|
| SPIKE-01 | Prototype client-side OCR vs. server-side OCR on real photos | Done | ADR-005: server-side primary; 87.9% avg conf, 2420ms avg latency, 0 errors on 46 photos | |
| SPIKE-02 | Prototype barcode mm-per-pixel calibration accuracy | Done | ADR-006+amendment: zxing-cpp chosen (no DLL); px>50 gate; 0.11-0.23 mm/px per-photo calibration confirmed | |

## Phase 1 â€” MVP

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
| AUTH-01 | `users` table + model | Not Started | |
| AUTH-02 | Password hashing + JWT issuance/refresh | Not Started | |
| AUTH-03 | `/auth/login`, `/auth/refresh` endpoints | Not Started | |
| AUTH-04 | Role-based access control middleware | Not Started | |
| AUTH-05 | Rate limiting on auth endpoints | Not Started | |

### Capture
| ID | Task | Status | Notes |
|---|---|---|---|
| CAP-01 | STOP â€” Stitch design checkpoint: Capture screen | Not Started | |
| CAP-02 | Camera capture logic + multi-image state | Not Started | |
| CAP-03 | Quality gate: blur detection | Not Started | |
| CAP-04 | Quality gate: glare/lighting detection | Not Started | |
| CAP-05 | Quality gate: perspective/crop/resolution/occlusion | Not Started | |
| CAP-06 | Per-failure specific retake messaging | Not Started | |
| CAP-07 | Offline capture queue (Dexie.js/IndexedDB) | Not Started | |
| CAP-08 | `POST /inspections`, `POST /inspections/{id}/images` | Not Started | |
| CAP-09 | Resumable per-item sync on reconnect | Not Started | |

### Preprocessing
| ID | Task | Status | Notes |
|---|---|---|---|
| PRE-01 | Preprocessing pipeline scaffold | Not Started | |
| PRE-02 | Perspective correction + deskew | Not Started | |
| PRE-03 | Glare suppression + text-region enhancement | Not Started | |

### OCR
| ID | Task | Status | Notes |
|---|---|---|---|
| OCR-01 | Integrate PaddleOCR PP-OCRv6 | Not Started | |
| OCR-02 | Tesseract fallback path | Not Started | |
| OCR-03 | Retain text + confidence + bbox + source-image ref | Not Started | |

### Declaration Extraction
| ID | Task | Status | Notes |
|---|---|---|---|
| EXT-01 | Field extractor scaffold + persistence | Not Started | |
| EXT-02 | Extract: MRP | Not Started | |
| EXT-03 | Extract: net quantity | Not Started | |
| EXT-04 | Extract: manufacturer/packer/importer address | Not Started | |
| EXT-05 | Extract: month/year of manufacture | Not Started | |
| EXT-06 | Extract: consumer care details | Not Started | |
| EXT-07 | Extract: country of origin | Not Started | |
| EXT-08 | Extract: commodity name | Not Started | |
| EXT-09 | Commodity-category selection | Not Started | |

### Optical Calibration
| ID | Task | Status | Notes |
|---|---|---|---|
| CAL-01 | Barcode detection + known-width lookup | Not Started | |
| CAL-02 | mm-per-pixel scale derivation + persistence | Not Started | |
| CAL-03 | Uncalibrated fallback path | Not Started | |

### Rule Engine
| ID | Task | Status | Notes |
|---|---|---|---|
| RULE-01 | `rule_packs` table + JSON schema validation | Not Started | |
| RULE-02 | Author initial (v1) core rule pack | Not Started | |
| RULE-03 | Author font-height-by-PDP-area rule | Not Started | |
| RULE-04 | Rule engine core (dispatch + evaluate) | Not Started | |
| RULE-05 | `GET /rule-packs`, `GET /rule-packs/{version}` | Not Started | |
| RULE-06 | `POST /rule-packs`, activate endpoint (admin) | Not Started | |
| RULE-07 | Freeze `inspections.rule_pack_version` at creation | Not Started | |

### Evidence Mapping
| ID | Task | Status | Notes |
|---|---|---|---|
| EVID-01 | Bind fields + violations to bounding boxes | Not Started | |
| EVID-02 | `violations` table population from rule engine | Not Started | |
| EVID-03 | STOP â€” Stitch design checkpoint: Evidence viewer | Not Started | |

### Human Review
| ID | Task | Status | Notes |
|---|---|---|---|
| REV-01 | Confidence-threshold routing to review queue | Not Started | |
| REV-02 | `PATCH /inspections/{id}/fields/{field_id}` | Not Started | |
| REV-03 | Immutable audit-log write on override | Not Started | |
| REV-04 | STOP â€” Stitch design checkpoint: Review Queue screen | Not Started | |

### Reporting
| ID | Task | Status | Notes |
|---|---|---|---|
| RPT-01 | WeasyPrint PDF report template | Not Started | |
| RPT-02 | Shared, un-omittable legal disclaimer partial | Not Started | |
| RPT-03 | `POST /inspections/{id}/report` + R2 upload | Not Started | |
| RPT-04 | Editable-format export | Not Started | |

### Storage & Sync
| ID | Task | Status | Notes |
|---|---|---|---|
| STOR-01 | Cloudflare R2 integration (signed URLs) | Not Started | |
| STOR-02 | Neon Postgres provisioning + connection wiring | Not Started | |
| STOR-03 | Local storage cap + low-space warning | Not Started | |

### Search & History
| ID | Task | Status | Notes |
|---|---|---|---|
| SRCH-01 | `GET /inspections` with filters | Not Started | |
| SRCH-02 | STOP â€” Stitch design checkpoint: Search/History screen | Not Started | |

### Testing & Acceptance
| ID | Task | Status | Notes |
|---|---|---|---|
| TEST-01 | Unit tests: rule engine, calibration, extraction | Not Started | |
| TEST-02 | Integration test: full pipeline on real sample photos | Not Started | |
| TEST-03 | Verify every MVP acceptance criterion in `01_PRD.md` Â§6 | Not Started | |
| TEST-04 | SQLite â†” Postgres JSON round-trip test | Not Started | |

### Deploy (MVP)
| ID | Task | Status | Notes |
|---|---|---|---|
| DEPLOY-01 | Deploy backend to Render free Web Service | Not Started | |
| DEPLOY-02 | Deploy frontend to Cloudflare Pages | Not Started | |
| DEPLOY-03 | Confirm cold-start handling works end-to-end | Not Started | |
| DEPLOY-04 | Full secrets checklist walkthrough against live deploy | Not Started | |

## Phase 2 â€” Enhanced Features

| ID | Task | Status | Notes |
|---|---|---|---|
| E2-01 | Extract remaining declaration fields (full set) | Not Started | |
| E2-02 | Full font/legibility rule set (all variants) | Not Started | |
| E2-03 | Multi-image cross-matching | Not Started | |
| E2-04 | Full human review workflow polish | Not Started | |
| E2-05 | Analytics dashboard | Not Started | |
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

- [ ] Every ID in `07_IMPLEMENTATION_PLAN.md` appears exactly once here.
- [ ] Every ID here appears exactly once in `07_IMPLEMENTATION_PLAN.md`.
- [ ] No task title has silently diverged between the two files.
- [ ] The "Last updated" line above is current.

If this checklist ever fails, fixing it is the immediate next task â€” before starting anything else â€” because every downstream session-start/session-continue check trusts this file to be complete.






