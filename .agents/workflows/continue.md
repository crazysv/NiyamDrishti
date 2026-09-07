---
description: session continue
---

## Checklist

1. **Read `docs/08_TRACKER.md`.** Find any task marked `In Progress` — that's very likely where you left off. If none are `In Progress`, find the next `Not Started` task respecting dependencies in `docs/07_IMPLEMENTATION_PLAN.md`.
2. **Read that task's full entry in `docs/07_IMPLEMENTATION_PLAN.md`** — don't rely on the tracker's one-line title alone; it deliberately doesn't carry the full detail.
3. **Read the last few entries of `docs/CHANGELOG.md`** to confirm what was actually completed most recently — this is your best signal for "where exactly did I stop," better than assuming from the tracker status alone.
4. **Check `docs/10_OPEN_QUESTIONS.md`** for anything `Open` tagged to the current task's area — resolve it if you can, or continue respecting the logged working assumption if not.
5. **If the current task touches UI:** confirm whether a Stitch design was already provided for it. If yes, continue building against it. If no, **stop and ask the user for it** before writing UI code (`docs/05_DESIGN.md`) — don't assume a previous session already handled this without checking.
6. **Resume work** on the identified task, following the standard work loop in `AGENTS.md` §5.
7. **Before ending this session too:** make sure `docs/08_TRACKER.md` reflects true current status, `docs/CHANGELOG.md` has an entry for whatever you completed this session, and any decisions/ambiguities from this session are logged in `docs/09_DECISIONS.md`/`docs/10_OPEN_QUESTIONS.md`. Leaving these unsynced is exactly how the next session (yours or someone else's) loses track of real state.

---

## Quick sanity check before trusting the tracker

Skim-verify that the task you're about to resume actually looks like it's in the state the tracker claims (e.g., if it says `In Progress`, does partial code for it actually exist?). If it doesn't match, don't just proceed — switch to `docs/13_RECOVERY.md`, because that mismatch is the exact failure pattern this whole doc system was built to catch early.

---

