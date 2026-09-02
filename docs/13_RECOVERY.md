# 13_RECOVERY — What To Do When Things Get Lost

This file is for exactly one situation: you (an AI agent, or a human) need to pick this project up **without trusted continuity** — a fresh context window, a new agent session, a long gap since the last session, or a sense that the project may have drifted from its docs. If you already know exactly where things stand and are just continuing normal work, use `session-continue.md` instead — it's the lighter-weight version of this file for the common case.

---

## Step 1 — Re-anchor on what the project is

Read, in order:
1. `AGENTS.md` (if you haven't already loaded it)
2. `MASTER_CONTENT.md` (at least skim every section heading; read fully if this is truly a cold start)
3. `docs/12_GUARDRAILS.md`

Do not skip to code. Code without this context is exactly how drift happens.

## Step 2 — Establish real project state

1. Read `docs/08_TRACKER.md` in full. Note every task marked `Done`, `In Progress`, and `Blocked`.
2. Read `docs/07_IMPLEMENTATION_PLAN.md` in full. **Run the parity check**: does every ID in one file appear in the other? If not, stop here and fix parity first (`docs/12_GUARDRAILS.md` §2) — do not proceed with feature work on top of a tracker you can't trust.
3. Read `docs/CHANGELOG.md`'s most recent entries to understand what actually shipped recently, in the project's own words, not just tracker checkboxes.
4. Read `docs/09_DECISIONS.md` for the most recent entries — has anything material changed since the docs you're about to trust were written?
5. Read `docs/10_OPEN_QUESTIONS.md` — are there `Open` items that block what you're about to do?

## Step 3 — Detect drift (compare code against docs, not the other way around)

If you suspect the actual codebase may have drifted from what the tracker claims:
1. Pick a handful of tasks marked `Done` in `docs/08_TRACKER.md`, spread across different modules.
2. For each, verify the described behavior actually exists in the code — not just that *some* related code exists, but that it matches the task's intent in `docs/07_IMPLEMENTATION_PLAN.md` and, if applicable, the acceptance criteria in `docs/01_PRD.md`.
3. If you find a mismatch (code doesn't do what the tracker claims, or does something the docs never asked for), do **not** silently fix the tracker to match the code, and do **not** silently delete the unplanned code. Log it explicitly:
   - If the code is wrong/incomplete relative to the spec: revert the task's tracker status to `In Progress` or `Blocked`, note why in the tracker's Notes column, and add a `docs/CHANGELOG.md` entry describing the discrepancy found.
   - If the code did something genuinely useful but out of scope (drift in the "built extra" direction): flag it in `docs/10_OPEN_QUESTIONS.md`, and ask the user whether to keep it (retroactively scope it into a task) or remove it — don't decide unilaterally either way.
4. For a full, structured version of this check, run the audit in `docs/14_TRANSLATION_AUDIT.md`.

## Step 4 — Resume work

Once state is trustworthy again:
1. Pick the next `Not Started` (or unblocked `In Progress`) task in `docs/08_TRACKER.md`, respecting its `Depends on` chain in `docs/07_IMPLEMENTATION_PLAN.md`.
2. Follow the standard work loop in `AGENTS.md` §5.

## Step 5 — If the drift is severe (a significant chunk of work doesn't match the spec)

1. Don't panic-rewrite. Document the actual current state honestly first (Step 3 above, applied broadly).
2. Present the user with a clear picture: what the docs say should exist, what actually exists, and the gap — let the user decide whether to re-scope the docs to match reality (if the drift was actually a good direction) or to correct the code (if it wasn't).
3. Whichever direction is chosen, update `docs/08_TRACKER.md` and `docs/07_IMPLEMENTATION_PLAN.md` together (parity procedure, `docs/12_GUARDRAILS.md` §2) so the docs are trustworthy again before continuing.

---

## The one thing to never do during recovery

Never assume the tracker is accurate without spot-checking it against real code at least once per recovery. The entire reason this file exists is that a previous version of this project's tracker looked complete and wasn't. Trust, but verify — every time you're picking this project up without continuity.
