# 14_TRANSLATION_AUDIT — Spec-to-Code Fidelity Audit

**"Translation" here means the translation of *specification into implementation*** — did what the docs asked for actually end up faithfully built in code, with nothing lost, substituted, or silently reinterpreted along the way? This is the periodic, structured version of the spot-check described in `13_RECOVERY.md` Step 3. Run it at the end of every phase (at minimum), and any time something feels like it might have quietly drifted.

*(This file has a second, smaller purpose too — §3 below tracks actual language/i18n coverage, since the project has a real multilingual dimension in Phase 3. Don't confuse the two purposes when reading or writing entries — they're separated below.)*

---

## Part 1 — Fidelity Audit

### How to run one
1. Pick a doc to audit against: usually `01_PRD.md` (user stories) or `MASTER_CONTENT.md` §10 (feature specs).
2. For each requirement/user story, find the task(s) in `07_IMPLEMENTATION_PLAN.md` that were supposed to build it.
3. Confirm those tasks are marked `Done` in `08_TRACKER.md`.
4. **Actually exercise the built feature** (run it, don't just read the code) and check it against the requirement's acceptance criteria, word for word.
5. Record the result below — pass, gap, or drift (built something different from what was asked).

### Audit Log

```
## Audit — YYYY-MM-DD (after Phase N)
Audited against: <doc + section>
| Requirement | Linked task(s) | Tracker status | Actually verified? | Result |
|---|---|---|---|---|
| US-01 ... | CAP-02..CAP-09 | Done | Yes/No | Pass / Gap / Drift — <detail> |
...
Summary: <overall finding>
Follow-up actions logged: <link to CHANGELOG entries / tracker status changes / new Open Questions>
```

*(No audits have run yet — this project is at the documentation-setup stage. The first audit should happen at the end of Phase 1, checking every `01_PRD.md` §4 user story against `01_PRD.md` §6's MVP acceptance criteria.)*

### What counts as "Drift" vs. "Gap"
- **Gap** — something specified was simply not built yet (should map to a `Not Started`/`In Progress`/`Blocked` tracker status — if the tracker says `Done` but there's a Gap, that's a tracker-accuracy bug, fix it immediately).
- **Drift** — something *was* built, but doesn't match what was asked (a different UI than Stitch specified, a rule hard-coded instead of data-driven, a scope-expanded or scope-reduced version of a task). Drift is the more serious finding — it means the docs and the code have diverged even though the tracker might look clean. Every Drift finding gets a `CHANGELOG.md` entry and, if it changes future direction, a `09_DECISIONS.md` entry.

---

## Part 2 — Language / i18n Coverage Tracking

Tracks actual (not planned) language support in the product, since the OCR/rule-checking pipeline's language coverage is a real, evolving fact about the built system — separate from the fidelity-audit purpose above.

| Language | OCR coverage status | UI translation status | Notes |
|---|---|---|---|
| English | MVP target (Phase 1) | MVP target | Primary language for Phase 1/2 |
| Hindi (Devanagari) | Not yet verified | Not started | See `10_OPEN_QUESTIONS.md` OQ-07 — verify before `E3-04` |
| Other scheduled Indian languages (via Bhashini, Phase 3) | Not started | Not started | Deferred to Phase 3 (`E3-03`, `E3-04`) |

Update this table as Phase 3 language work actually happens — it should reflect **what the running system supports today**, not the aspiration in `MASTER_CONTENT.md` §10.13.
