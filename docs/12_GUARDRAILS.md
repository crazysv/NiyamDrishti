# 12_GUARDRAILS — The Anti-Drift Rulebook

This is the single most important process document in this repo. It exists because a previous attempt at this project drifted: an AI coding agent built something other than what was intended, and the root cause was traced to the documentation itself being incomplete and inconsistent — specifically, `08_TRACKER.md`'s predecessor didn't contain everything `02_ROADMAP.md`'s predecessor did, so "check the tracker, keep going" left real scope silently unbuilt while the agent moved on to things that weren't actually next.

Every rule below is written to close a specific way that failure could happen again. Read it before writing code. Re-read it if you (the agent) notice yourself about to do something "reasonable" that isn't explicitly asked for in `07_IMPLEMENTATION_PLAN.md`.

---

## 1. Document precedence (what wins when things conflict)

1. **`MASTER_CONTENT.md`** — describes what the project *is*. Wins by default over any derived doc.
2. **A later, more specific entry in `09_DECISIONS.md`** — overrides Master Content *for that specific point only*, because it represents a real decision made with more context than the original research had.
3. **All other docs** (`01_PRD.md` through `14_TRANSLATION_AUDIT.md`) are derived, task-specific views. If two derived docs disagree with each other, **that is a bug** — it means one of them went stale. Log it in `10_OPEN_QUESTIONS.md`, fix the stale one immediately, and don't just silently pick one and proceed.

## 2. Tracker/Plan parity procedure (the specific fix for the original failure)

`08_TRACKER.md` must always contain exactly the same task IDs as `07_IMPLEMENTATION_PLAN.md` — no more, no fewer, no silently reworded titles that drift from each other over time.

**The procedure, every time either file changes:**
1. Decide the change (add/split/merge/remove/rescope a task) in `07_IMPLEMENTATION_PLAN.md` first — this is the authority on *what* the task is.
2. Make the identical structural change in `08_TRACKER.md` in the **same turn** — same ID, same title, plus its status.
3. Run the parity checklist at the bottom of `08_TRACKER.md` before ending that turn.
4. Note the change in `CHANGELOG.md`.

**Never** update one file and leave the other for "later" — later is exactly how the original drift happened.

## 3. The free-tier-only rule, operationalized

Before introducing **any** new tool, library-as-a-service, or hosted dependency:
1. Check `MASTER_CONTENT.md` §11 — is an equivalent choice already made? Use it.
2. If genuinely new, verify: is it free, or does it have a real, usable free tier?
3. **Specifically check for the Resend trap:** does using the free tier *properly* (production-grade, not a toy) require something paid — a custom domain, a credit card that gets charged past a soft limit, a "free" tier that's actually a time-limited trial? If yes, do not make it the default; at most, note it as a documented future/paid option per `MASTER_CONTENT.md` §16.
4. Log the choice (and the free-tier verification) in `09_DECISIONS.md`.

If you are ever unsure whether something satisfies this rule, **stop and ask the user** rather than guessing — this constraint was stated as a hard requirement, not a preference.

## 4. Definition of done (applies to every task in `07_IMPLEMENTATION_PLAN.md`)

A task is not done until **all** of the following are true:
- [ ] The code/artifact actually works as specified (matches the linked doc references for that task).
- [ ] `08_TRACKER.md` status is updated for that exact task ID.
- [ ] `CHANGELOG.md` has a dated entry.
- [ ] If a non-trivial decision was made along the way, it's in `09_DECISIONS.md`.
- [ ] If an ambiguity was hit, it's in `10_OPEN_QUESTIONS.md` (even if you made a reasonable assumption and kept moving — log the assumption).
- [ ] If the task touched a UI screen, it was built against a real Stitch export, not an agent-invented design (rule 5 below).

Marking a task "Done" in the tracker without these is itself a drift risk — it makes the tracker lie about project state, which is exactly the failure mode this whole doc set exists to prevent.

## 5. The Stitch/frontend rule (repeated here because it's the highest-risk drift point)

**Never design a UI yourself.** The user's Stitch account, via the Stitch MCP server, is the design tool of record. The moment a task requires deciding what a screen looks like, stop and ask the user to generate it in Stitch. Full detail: `05_DESIGN.md`. This is restated in three places (`AGENTS.md`, `05_DESIGN.md`, here) deliberately — it is the single most likely place an agent "helpfully" drifts by shipping a placeholder UI that becomes permanent under time pressure.

## 6. Scope discipline (both directions)

- **Don't build ahead of the current phase.** Check `02_ROADMAP.md` / the task's phase tag in `07_IMPLEMENTATION_PLAN.md` before building something that "seems useful" or "is easy since you're already in that code." A Phase 2/3/4 feature built early during Phase 1 is unbudgeted, untested-in-context work that steals time from what the current phase actually needs.
- **Don't quietly drop scope either.** If a task in `07_IMPLEMENTATION_PLAN.md` turns out to be harder than expected, don't silently simplify it and mark it done — split it (see the parity procedure), mark the remainder `Blocked` or `In Progress`, and say so.
- Both directions are the same underlying failure: the tracker no longer reflecting reality.

## 7. Never fabricate a legal citation

If a rule/section number, sub-clause letter, or amendment date isn't verified, mark it `[VERIFY]` everywhere it appears — in code comments, in the rule-pack JSON `citation` field, and in report templates — rather than presenting an unverified guess as fact. See `10_OPEN_QUESTIONS.md` OQ-02/OQ-04 for the specific citations already flagged as unverified. A wrong legal citation on an inspection report is a real-world credibility risk for the product's core value proposition (evidentiary trust), not a cosmetic detail.

## 8. Rules are data (repeated because it's easy to violate accidentally)

Never write a Legal Metrology threshold (a font-size mm value, an MRP-format check, a category-specific exemption) directly into application/validation code. It belongs in a `rule_packs.rules_json` entry (`06_SCHEMA.md` §3). If you catch yourself about to write `if font_height_mm < 2.0:` anywhere in application code with a bare literal, stop — that literal should be read from the active rule pack instead.

## 9. When to stop and ask the human (consolidated list)

- A UI/screen design is needed (rule 5).
- A required secret/API key isn't in `11_SECRETS_CHECKLIST.md` yet.
- Two documents genuinely conflict and it's unclear which is stale.
- A legal/regulatory citation can't be verified and the current task needs to print it on user-facing output.
- You're evaluating a new tool/service and aren't fully sure it clears the free-tier rule (§3).
- A task in `07_IMPLEMENTATION_PLAN.md` seems to require government-integration access (eMaap, MeriPehchan, Bhashini approval, etc.) sooner than its scheduled phase.

Don't stop and ask for things reasonably decidable from the existing docs (internal code organization, naming, a library choice already implied by `03_TECHSPEC.md`) — over-asking is its own drag on progress. The bar is genuine ambiguity or a genuinely irreversible/consequential choice, not routine implementation detail.

## 10. If you're a fresh agent session picking this project up cold or mid-stream

Go to `13_RECOVERY.md` now. Do not attempt to infer project state from partial context or from skimming code alone — the docs in this repo exist specifically so you don't have to.
