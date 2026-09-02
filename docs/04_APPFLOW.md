# 04_APPFLOW — Application & User Flows

This document describes *behavior* (what happens, in what order, including edge cases). It does **not** describe visual design — no colors, layouts, or component styling here. Visual design comes from the user's Stitch account per `05_DESIGN.md`. This file is what the agent builds the *logic/state machine* against; Stitch exports are what the agent builds the *pixels* against.

---

## 1. Officer — Core Inspection Flow

```
[Login] → [Home / New Inspection] → [Capture] → [Quality Check]
   → (fail) → [Retake prompt with specific reason] → back to Capture
   → (pass) → [Add another image? y/n] → (y) loop Capture
                                        → (n) → [Processing state]
→ [Processing state] → [Results: per-declaration verdicts + evidence]
   → [Tap a field] → [Evidence viewer: bounding box highlighted on source image]
   → [Field below confidence threshold] → [Review queue item]
       → [Confirm as-is] or [Correct value] → [Audit log entry written]
→ [All fields reviewed] → [Generate report] → [Report preview / share / save]
→ [Return to Home]
```

### Key states & edge cases
- **Offline at any point:** capture and local processing (if client-side OCR is in use per the Phase 0 spike decision) continue to work; anything requiring the server queues with a visible "pending sync" indicator. The officer must never be blocked from continuing to the next package because a previous one hasn't synced yet.
- **Cold-start delay:** if the backend has been asleep (Render free-tier behavior), the processing state should show an indeterminate-but-reassuring state, not appear frozen or error out.
- **No barcode visible (calibration unavailable):** font-height verdicts must be visibly marked "uncalibrated / estimated" rather than presented with false precision (`MASTER_CONTENT.md` §9.4).
- **Multiple images needed for one commodity category** (e.g., a pan-masala pack needing a distinct RSP field check): the flow supports adding more than one image to the same inspection before processing.
- **Sticker over original print (common MRP-correction case):** the officer can flag which image is authoritative for a given field if the system's own cross-image matching produces a conflict; this manual flag itself gets logged, not silently resolved.

## 2. Officer — Review Queue Flow (zoomed in)

```
[Field flagged "Needs Review" — confidence below threshold]
   → [Show extracted value + confidence + evidence crop]
   → Officer choice:
        (a) [Confirm as correct] → verdict re-evaluated against rule pack → logged
        (b) [Correct the value] → officer types/edits → verdict re-evaluated → logged with before/after
        (c) [Mark as "not present / not applicable"] → logged with reason
   → [Next flagged field] or [Return to results if none remain]
```
Every path in (a)/(b)/(c) writes an immutable audit-log entry: officer id, timestamp, field id, action, before value, after value (if any).

## 3. Supervisor — Dashboard Flow

```
[Login] → [Dashboard]
   → [Filter: date range / officer / region / violation type / product]
   → [Trend view: compliance rate over time, violation hotspots]
   → [Drill into a specific inspection] → [Same evidence viewer as Officer flow, read-only]
   → [Export summary]
```

## 4. Administrator — Rule Pack & User Management Flow

```
[Login] → [Admin panel]
   ├── [User management] → [Add/edit/deactivate officer or supervisor accounts]
   └── [Rule pack management]
         → [View current active rule pack version]
         → [Upload new rule-pack JSON] → [Validate against schema] → (fail) show specific validation errors
                                                                    → (pass) → [Review diff vs. active version]
         → [Activate new version] → [Confirmation — this affects all NEW inspections from this point forward,
                                      past inspections keep their recorded rule-pack version, unchanged]
```
**Critical invariant:** activating a new rule pack must never retroactively change the recorded verdict of a past inspection. Past inspections always show the rule-pack version that was active when they were performed (`01_PRD.md` US-04 acceptance criterion).

## 5. (Future, Phase 3+) Manufacturer Self-Check Flow

Structurally separate from the Officer flow above — reuses the same underlying pipeline (capture → extract → validate → evidence) but:
- Does **not** write to the enforcement `inspections` table used for official records.
- Is clearly labeled as a self-check tool, not an official inspection, in the UI copy and in any exported report.
- Does not appear in Supervisor/Admin enforcement dashboards.

This separation is a hard product requirement (`01_PRD.md` NG4), not a styling choice — do not implement this by simply hiding a flag on the same record type; use a genuinely separate data path.

## 6. Cross-cutting edge cases (apply to every flow above)

| Edge case | Required behavior |
|---|---|
| Device storage nearly full (offline queue) | Warn the officer before it silently fails to queue a new capture |
| Very low light / unusable image | Reject at the quality gate with a specific, actionable reason (§10.1 Master Content) — never pass a useless image through to OCR |
| Ambiguous commodity category (affects which rule variant applies, e.g., pan masala RSP rule) | Prompt for a manual category selection rather than guessing silently |
| Officer session expires mid-inspection | Preserve in-progress local work; re-auth without losing captured-but-unsynced data |
| Rule pack fails validation on upload (Admin flow) | Show the specific schema violation, never silently reject with a generic error |
