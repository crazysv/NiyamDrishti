# CHANGELOG

All notable changes to the actual, running project are logged here, dated, in reverse-chronological order (newest first). This is a record of what's **actually built and working**, not a restatement of the roadmap or the tracker â€” those describe intent; this describes reality.

Format per entry: `### YYYY-MM-DD â€” <short summary>` followed by bullet points of what changed. Reference task IDs from `07_IMPLEMENTATION_PLAN.md` where relevant.

---

## [Unreleased]

Nothing shipped yet â€” the project is at the documentation/planning stage.

### 2026-09-02 — Phase 0 Spikes complete (SPIKE-01, SPIKE-02)
- **SPIKE-01 (OCR):** Ran PaddleOCR 2.9.1 on 46 real label photos. 0 errors, 87.9% avg confidence, 2420ms avg latency. Decision: server-side primary for Phase 1 (ADR-005). OQ-03 resolved.
- **SPIKE-02 (Calibration):** Barcode px-width unreliable via OpenCV BarcodeDetector. Tested zxing-cpp: 6/8 photos decoded correctly, no DLL dependencies. Decision: zxing-cpp as primary detector, px>50 gate, uncalibrated fallback mandatory (ADR-006 + amendment). OQ-04 updated.
- Phase 0 complete. Next: SETUP-01.

### 2026-09-02 â€” Documentation system created
- Created `MASTER_CONTENT.md`, `AGENTS.md`, `session-start.md`, `session-continue.md`, and the full `docs/` folder (`00_README.md` through `14_TRANSLATION_AUDIT.md`) to replace the previous, incomplete doc set that led to the AI coding agent drifting off-spec on a prior attempt.
- Established `docs/07_IMPLEMENTATION_PLAN.md` and `docs/08_TRACKER.md` as a strictly 1:1-parity pair â€” the specific structural fix for the original tracker/roadmap mismatch.
- Verified the full technology stack in `MASTER_CONTENT.md` Â§11 against independent research (not just the originally-provided AI research) for genuine free-tier status as of September 2026, explicitly checking each choice against the "Resend trap" (a free tool with a hidden paid dependency).
- Seeded `docs/09_DECISIONS.md` with four initial architecture decisions (ADR-001 through ADR-004) and `docs/10_OPEN_QUESTIONS.md` with seven open questions (OQ-01 through OQ-07) found during research, so unresolved items are tracked from day one rather than forgotten.
- No code written yet. Next step per `docs/02_ROADMAP.md`: Phase 0 spikes (`SPIKE-01`, `SPIKE-02`).

---

*(New entries go at the top, under `[Unreleased]` until a real release/milestone tag is meaningful for this project â€” likely not before a Phase 1 MVP demo.)*








