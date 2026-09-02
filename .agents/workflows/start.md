---
description: session start
---

You are starting a **new session** on the SIH26034 Legal Metrology Label Compliance Platform. Before doing anything else, work through this checklist in order.

---

## Checklist

1. **Read `AGENTS.md`** at the repo root in full. This has your operating rules and the document map.
2. **Read `MASTER_CONTENT.md`** in full (or, if you've read it in a previous session and it hasn't changed, confirm that via its content — don't assume, actually check for recent edits by skimming `docs/CHANGELOG.md` for any Master Content updates).
3. **Read `docs/12_GUARDRAILS.md`** in full — this is the anti-drift rulebook. Internalize it, don't just skim it.
4. **Read `docs/08_TRACKER.md`** in full. This is current project state.
5. **Run the parity check** described at the bottom of `docs/08_TRACKER.md`: does every task ID in `docs/07_IMPLEMENTATION_PLAN.md` appear there and vice versa? If not, **stop and fix parity before doing anything else** (`docs/12_GUARDRAILS.md` §2).
6. **Read the most recent entries in `docs/CHANGELOG.md`** — what actually shipped most recently, in plain language.
7. **Read the most recent entries in `docs/09_DECISIONS.md`** — any recent decisions that change how you should approach upcoming work.
8. **Check `docs/10_OPEN_QUESTIONS.md`** for any `Open` items relevant to the task you're about to pick up.
9. **Identify the next task**: the first `Not Started` (or unblocked `In Progress`) task in `docs/08_TRACKER.md`, respecting its dependencies in `docs/07_IMPLEMENTATION_PLAN.md`.
10. **State your plan to the user** in one short paragraph before starting: which task, why it's next, and — if it's a UI task — an explicit note that you'll need a Stitch design before building the screen (`docs/05_DESIGN.md`).
11. Begin work, following the standard work loop in `AGENTS.md` §5.

---

## If anything in steps 1–8 feels inconsistent, incomplete, or like the project state doesn't add up

Do not proceed on the assumption everything is fine. Switch to the full recovery protocol: `docs/13_RECOVERY.md`.

---

## Where to put this file (so it works as a real slash command)

Drop this file into whichever slash-command folder your IDE/agent tool uses, for example:
- **Claude Code:** `.claude/commands/session-start.md`
- **Cursor:** `.cursor/commands/session-start.md` (or your configured commands directory)
- **Windsurf:** the equivalent `workflows`/`commands` folder for your Windsurf version

Check your specific tool's current docs for the exact folder name if these have changed — the content of this file itself doesn't depend on where it lives.
