# 02_ROADMAP — Phase-Level Roadmap

This is the **high-level "when"**. For the granular, checkable "how," see `07_IMPLEMENTATION_PLAN.md` — every task there is tagged with the phase it belongs to, and that tag is the authority on scope, not this file's prose. If this file and `07` ever disagree on which phase something belongs to, `07` + `08_TRACKER.md` win; fix this file to match and log the correction in `CHANGELOG.md`.

**Key context date:** SIH 2026 submission deadline is **20 September 2026**. Phase 0 and Phase 1 below are the hackathon-critical path. Phases 2–4 are explicitly post-hackathon and must never be pulled forward at the expense of Phase 1 completeness.

---

## Phase 0 — Spikes (before any feature work)

**Goal:** de-risk the two biggest unknowns before committing real build time to them.

- Spike A: Client-side OCR (PaddleOCR.js / Tesseract.js WASM) vs. server-side OCR — test real accuracy/speed on representative label photos on a mid-range Android phone. See `MASTER_CONTENT.md` §11.3.
- Spike B: Barcode-based mm-per-pixel calibration accuracy (`MASTER_CONTENT.md` §9.4) on real photos at realistic capture angles/distances.

**Exit criterion:** both spikes have a written decision in `09_DECISIONS.md` before Phase 1 begins.

## Phase 1 — MVP (hackathon-critical path)

**Goal:** the core capture → OCR → extract → rule-check → evidence → report loop, working end-to-end, for physical packages, offline-capable, on the free stack.

Scope (see `07_IMPLEMENTATION_PLAN.md` for the task-level breakdown):
- Capture module with quality gates (US-01, US-02)
- Preprocessing pipeline
- OCR + declaration extraction for the core mandatory-declaration set (§4.2 Master Content)
- Versioned rule engine, seeded with the core rule pack
- Evidence mapping (bounding boxes)
- Basic human review queue
- PDF report generation with the mandatory disclaimer
- Local/offline-first storage (SQLite/local + sync queue)
- Basic officer authentication

**Definition of done:** matches `01_PRD.md` §6 "Acceptance Criteria for MVP Done" exactly.

## Phase 2 — Enhanced Features (post-hackathon, weeks ~4–8)

**Goal:** complete the full declaration set and make the system pilot-ready.

- Full declaration extraction (all fields in §4.2, not just the core set)
- Font/legibility validation with the calibration technique fully wired (not spike-only)
- Multi-image support (front/back/sticker cross-matching)
- Full human review workflow with audit trail
- Analytics dashboard (Supervisor/Admin)
- Production data layer wiring: Neon Postgres + Cloudflare R2 (replacing local-only storage)
- Rule-pack management UI for Administrators

## Phase 3 — E-commerce & Advanced (weeks ~8–12)

- E-commerce listing cross-consistency checking
- Bhashini integration (vernacular voice UI / Indic-language assist) — **only after confirming current sign-up/approval status; never block other Phase 3 work on it**
- Batch/warehouse scanning mode
- (If scoped) Manufacturer/Packer self-check mode — must be a structurally separate mode from enforcement inspections (`01_PRD.md` NG4)

## Phase 4 — Production Readiness (weeks ~12–16+)

- Government SSO (MeriPehchan/Jan Parichay) replacing self-rolled auth
- Hardened offline sync (conflict resolution, retry/backoff, storage-limit handling)
- Monitoring/observability
- Full deployment checklist finalized in `03_TECHSPEC.md`/`11_SECRETS_CHECKLIST.md`
- eMaap API adapter (aspirational — contingent on an actual available integration point; do not build blind)
- Formal security review of the audit-log/evidence chain for evidentiary use

---

## Rule for the agent: don't skip ahead

If a Phase 2+ item looks easy to build while you're already inside related code, **do not build it early**. Log it as a note in `10_OPEN_QUESTIONS.md` or `09_DECISIONS.md` if it changes how you'd structure the current Phase 1 code, but the actual feature stays unbuilt until its phase. Scope creep in this direction is exactly as damaging as building the wrong thing outright — it consumes time the current phase needed and produces untested, unintegrated code sitting in the tree.
