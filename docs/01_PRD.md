# 01_PRD — Product Requirements Document

**Product:** NiyamDrishti (SIH26034) — Legal Metrology Label Compliance Platform
**Status:** Draft → build in progress (see `08_TRACKER.md` for live status)
**Source of truth for context:** `../MASTER_CONTENT.md` — this document formalizes that context into testable requirements. If a requirement here ever seems to contradict Master Content, Master Content wins; fix this file.

---

## 1. Goals

**G1.** Reduce the time to fully inspect one packaged product's label from ~10–15 minutes (manual) to under 2 minutes (assisted).
**G2.** Produce compliance findings that are traceable to specific visual evidence (bounding boxes on the source image), not just text assertions.
**G3.** Keep the compliance rule logic upgradable without a code deployment, so regulatory amendments don't require an engineering cycle.
**G4.** Work fully offline in the field, syncing when connectivity returns.
**G5.** Run entirely on a free (or generous-free-tier) tech stack with no hidden paid dependency.
**G6.** Never present an AI finding as a legal ruling — the officer always makes the final call.

## 2. Non-goals (explicitly out of scope for this product)

- **NG1.** This is not a replacement for eMaap (licensing/registration/verification). See `MASTER_CONTENT.md` §3.4/§5.
- **NG2.** This is not a pre-print brand/artwork QA tool (that's the Product Label Guru / Seventeen29 space).
- **NG3.** This does not issue penalties or legally binding verdicts.
- **NG4.** A consumer-facing "scan before you buy" mode is not in scope until Phase 3 (see `02_ROADMAP.md`) and must never be built early just because it reuses the same pipeline.
- **NG5.** Native mobile apps are out of scope unless/until the PWA genuinely can't meet a requirement (see `03_TECHSPEC.md` §Mobile).
- **NG6.** Any government API integration (eMaap adapter, MeriPehchan SSO, UMANG, DigiLocker) is out of scope until explicitly scheduled in the roadmap — these depend on external approval processes outside this project's control.

## 3. Personas

See `MASTER_CONTENT.md` §8 for full detail. Summary:

| Persona | Primary need |
|---|---|
| Legal Metrology Officer (LMO) | Fast, reliable, offline-capable field inspection |
| Enforcement Supervisor | Trend visibility across a team's inspections |
| Department Administrator | User management + rule-pack version control |
| (Future) Manufacturer/Packer | Self-check before market release — structurally separate from enforcement records |

## 4. User Stories & Functional Requirements

Each story has an ID (`US-xx`) referenced by tasks in `07_IMPLEMENTATION_PLAN.md`. "Acceptance criteria" here are the testable bar — a task isn't done until its linked story's acceptance criteria pass.

### Capture & Preprocessing
- **US-01** — As an LMO, I can capture one or more photos of a package (front, back, side, sticker) in a single inspection session, online or offline.
  *Acceptance:* multi-image capture works with zero connectivity; images queue locally and are visibly marked "pending sync."
- **US-02** — As an LMO, I get immediate, specific feedback if a photo is unusable (blur/glare/bad angle/low-res/too dark/occluded), before it wastes an OCR pass.
  *Acceptance:* each quality-check failure gives a distinct, actionable message — never a generic "bad photo."

### Extraction & Validation
- **US-03** — As an LMO, the system extracts every mandatory declaration (§MASTER_CONTENT.md §4.2) from the captured images with a confidence score and a source bounding box per field.
  *Acceptance:* every extracted field is clickable/tappable and highlights its source region on the original image.
- **US-04** — As an LMO, each extracted field is validated against the currently active rule pack and shown as Pass / Fail / Needs Review.
  *Acceptance:* the rule pack version used is visible on the inspection record; changing the active rule pack never silently changes a *past* inspection's recorded verdict.
- **US-05** — As an LMO, font-height rules are checked in real physical millimeters where a calibration reference (e.g., a visible barcode) is available, and clearly marked "uncalibrated" otherwise.
  *Acceptance:* the report visibly distinguishes calibrated vs. uncalibrated font measurements — never presents an uncalibrated estimate as precise.

### Review & Reporting
- **US-06** — As an LMO, any field below the confidence threshold routes to a review queue where I can confirm/correct it, and my correction is permanently logged.
  *Acceptance:* every override is in the audit log with who/when/before/after — never a silent overwrite.
- **US-07** — As an LMO, I can generate a PDF (and editable-format) inspection report with evidence thumbnails and cited rules.
  *Acceptance:* the report includes the mandatory "decision-support, not a legal ruling" disclaimer (`MASTER_CONTENT.md` §10.9) on every single generated report, with no way to omit it.
- **US-08** — As an LMO/Supervisor, I can search and retrieve past inspections by product, officer, date range, region, and violation type.

### Dashboards
- **US-09** — As a Supervisor, I can see compliance trends, violation hotspots, and officer throughput on a dashboard.
- **US-10** — As an Administrator, I can manage officer accounts and manage rule-pack versions (upload, review, activate) without a code deploy.

### Offline & Sync
- **US-11** — As an LMO, if I lose connectivity mid-inspection, my work is not lost, and syncs automatically (and resumably) once connectivity returns.

## 5. Non-Functional Requirements

| NFR | Requirement |
|---|---|
| Performance | End-to-end single-package inspection (capture → verdicts shown) target: under 2 minutes including officer review time |
| Offline | Full capture + provisional extraction must function with zero connectivity (see `03_TECHSPEC.md` for the client/server OCR split decision) |
| Cost | Zero required paid dependency for the MVP to run end-to-end; see `MASTER_CONTENT.md` §11 for the verified stack |
| Auditability | Every human override of an AI-suggested field is permanently logged, never overwritten |
| Legal safety | Every user-facing report carries the decision-support disclaimer; no unverified rule citation may appear in report text |
| Accessibility (field use) | Usable one-handed, outdoors, in bright light — large touch targets, high-contrast states for pass/fail/review |
| Data retention | Inspection history is retained and searchable indefinitely by default (no auto-deletion without an explicit admin action) |

## 6. Acceptance Criteria for "MVP Done"

The MVP (`02_ROADMAP.md` Phase 1) is complete when:
1. An officer can capture a real physical package's label, offline, and get a provisional set of extracted declarations.
2. Each extracted declaration is validated against at least the core declaration set (§4.2 in Master Content) using a versioned rule pack.
3. Every field/violation is traceable to a bounding box on the source image.
4. A PDF report can be generated with the mandatory disclaimer.
5. All of the above runs on the free stack defined in `03_TECHSPEC.md` with zero paid dependency.
6. `08_TRACKER.md` shows every Phase 1 task in `07_IMPLEMENTATION_PLAN.md` as Done, with no scope silently dropped.

## 7. Open items

Any requirement-level ambiguity (not implementation-level — those go in `07`) gets logged in `10_OPEN_QUESTIONS.md`, not resolved silently here.