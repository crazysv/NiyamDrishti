# AGENTS.md — Operating Instructions for Any AI Coding Agent in This Repo

> This file is written **to you**, the coding agent. If your tool auto-loads `AGENTS.md` (Claude Code, Cursor, Windsurf, and most modern agentic IDEs do), you are reading this before doing anything else in this repo. If it didn't auto-load, and a human pointed you here, **stop and read it now before touching any file.**
>
> This project failed once already because an agent drifted off-spec — it built things the documents didn't ask for, and the tracker file didn't actually contain everything the roadmap did, so "check the tracker, keep going" left real scope silently unbuilt. Every rule below exists specifically to stop that from happening again. Follow them literally, not in spirit.

---

## 1. What this project is (one paragraph)

You are building **NiyamDrishti** (SIH26034): a tool that lets a Legal Metrology field officer photograph a packaged product's label and get back, in seconds, a rule-by-rule compliance report against the Legal Metrology (Packaged Commodities) Rules, 2011 — with every finding traceable to the exact pixels that produced it, working offline, on a 100%-free tech stack. Full detail: `MASTER_CONTENT.md`.

---

## 2. Required reading order (do not skip steps)

1. **This file (`AGENTS.md`)** — rules and reading order.
2. **`MASTER_CONTENT.md`** — full project understanding. Read this fully at least once per fresh session; skim relevant sections thereafter.
3. **`docs/12_GUARDRAILS.md`** — the specific behavioral rules you must never violate.
4. **`docs/08_TRACKER.md`** — the current state of the project: what's done, what's next.
5. **`docs/07_IMPLEMENTATION_PLAN.md`** — the specific task you're about to work on, in full detail.
6. Whatever other numbered doc your current task references (see the map in §4 below).

If you were invoked via a slash command, `session-start.md` or `session-continue.md` already walks you through this — those files exist so a human never has to repeat this instruction manually again. If you were **not** invoked via one of those commands but are about to do non-trivial work in this repo, follow this reading order yourself before writing code.

---

## 3. The non-negotiable rules

1. **Free-tier-only tech stack.** Every tool, service, or platform you introduce must be free, or have a genuinely usable free tier, with **no indirect paid dependency** (the canonical example to never repeat: a "free" email API that only works in production with a paid custom domain). If you're evaluating a new tool mid-build, check it against this rule *before* wiring it in, and prefer the exact choices already made in `MASTER_CONTENT.md` §11 / `docs/03_TECHSPEC.md` unless a logged decision in `docs/09_DECISIONS.md` says otherwise.
2. **Never invent frontend UI/UX design.** The user generates real screen designs in their own **Google Stitch** account via the **Stitch MCP server**. The moment your current task would require deciding what a screen actually looks like — layout, component choices, visual hierarchy — **stop and tell the user it's time to generate/export the design in Stitch**, then build against what they give you. Do not wireframe, do not guess, do not ship a placeholder UI and call it done. See `docs/05_DESIGN.md`.
3. **The Tracker and the Implementation Plan must never drift apart.** `docs/08_TRACKER.md` is a status mirror of `docs/07_IMPLEMENTATION_PLAN.md` — same task IDs, same scope, always. If you add, split, remove, or rescope a task in one, you edit the other **in the same turn**. This exact drift is what broke the project last time — treat it as a hard rule, not a suggestion.
4. **Rules are data, not code.** Never hard-code a Legal Metrology rule threshold directly into application logic. Every rule lives in a versioned rule-pack JSON entry (`docs/06_SCHEMA.md`). If a task seems to require hard-coding a legal threshold, stop and re-read `MASTER_CONTENT.md` §4/§12.2 — you're about to build the exact anti-pattern this project exists to avoid.
5. **Don't silently resolve an ambiguity.** If you hit a genuine ambiguity in the spec, an unverified legal citation, or a conflicting instruction across documents, log it in `docs/10_OPEN_QUESTIONS.md` and make the smallest reasonable assumption to keep moving — do not guess silently and do not block on it either. Note the assumption you made in the same log entry.
6. **Log real decisions.** Any non-trivial technical choice (a library swap, an architecture change, a rule interpretation) gets an entry in `docs/09_DECISIONS.md` at the time you make it, not retroactively.
7. **Definition of done includes the docs, not just the code.** A task in `docs/07_IMPLEMENTATION_PLAN.md` is not complete until: the code works, `docs/08_TRACKER.md` reflects it, `docs/CHANGELOG.md` has an entry, and (if applicable) `docs/09_DECISIONS.md` / `docs/10_OPEN_QUESTIONS.md` are updated. Do not mark a task done in the tracker while leaving these unsynced.
8. **Stay inside the current phase's scope.** Check `docs/02_ROADMAP.md` and `docs/07_IMPLEMENTATION_PLAN.md` before building something that "seems useful" — if it's tagged for a later phase, do not build it early just because it's easy or you're already in that part of the code. Scope creep in the *other* direction (skipping ahead) caused the original failure just as much as building the wrong thing.
9. **Never fabricate a legal citation.** If you're not sure a rule/section number is correct, say so explicitly in the code comment, the report template, and `docs/10_OPEN_QUESTIONS.md` — a wrong citation on a compliance report is a real-world credibility risk, not a cosmetic bug.
10. **When in doubt about precedence between documents:** `MASTER_CONTENT.md` describes what the project *is* and wins by default. A more specific, later-dated entry in `docs/09_DECISIONS.md` overrides it for that specific point only. Everything else (PRD, Tech Spec, Roadmap, etc.) is a derived, task-specific view — if two derived docs disagree with each other, that's a bug: log it in `docs/10_OPEN_QUESTIONS.md` and fix the stale one immediately, don't just pick one and move on silently.

---

## 4. Document map — what to read for what

| You're about to... | Read |
|---|---|
| Understand the project at all | `MASTER_CONTENT.md` |
| Start a session cold | `session-start.md` |
| Resume mid-task / after a context reset | `session-continue.md` |
| Write a user-facing feature | `docs/01_PRD.md` + `docs/04_APPFLOW.md` |
| Plan sequencing / check what phase you're in | `docs/02_ROADMAP.md` |
| Touch architecture, the tech stack, an API contract, or an NFR | `docs/03_TECHSPEC.md` |
| Build any screen or component | `docs/05_DESIGN.md` **first** — this is the Stitch stop-and-check gate |
| Touch the database or the rule-pack JSON shape | `docs/06_SCHEMA.md` |
| Pick up the next task / know exactly what to build | `docs/07_IMPLEMENTATION_PLAN.md` |
| Update project status | `docs/08_TRACKER.md` (must match 07 exactly) |
| Make a non-trivial technical choice | Log it in `docs/09_DECISIONS.md` |
| Hit an ambiguity or unverifiable fact | Log it in `docs/10_OPEN_QUESTIONS.md` |
| Need an API key / secret / env var | `docs/11_SECRETS_CHECKLIST.md` |
| Are unsure if something is allowed | `docs/12_GUARDRAILS.md` |
| Feel lost, or are picking up someone else's half-done work | `docs/13_RECOVERY.md` |
| Want to confirm the built code still matches the spec | `docs/14_TRANSLATION_AUDIT.md` |
| Want to know what's actually shipped so far | `docs/CHANGELOG.md` |

---

## 5. The standard work loop

1. Read `docs/08_TRACKER.md`. Find the next not-started (or in-progress) task.
2. Read that task's full entry in `docs/07_IMPLEMENTATION_PLAN.md` — don't work from the tracker's one-line summary alone.
3. Check `docs/05_DESIGN.md` if the task touches UI (Stitch gate, rule #2 above).
4. Check `docs/06_SCHEMA.md` if the task touches data.
5. Implement the smallest coherent unit of that task.
6. Update `docs/08_TRACKER.md` status for that task.
7. Add a `docs/CHANGELOG.md` entry.
8. If you made a non-trivial decision or hit an ambiguity, log it (`09` or `10`).
9. Move to the next task, or stop and report status to the user if the task requires their input (a design, a secret/API key, a business decision).

---

## 6. What "stop and ask the human" means in practice

Stop and explicitly ask, rather than guessing, when:
- You've reached the point where a screen's actual visual design is needed (Stitch handoff — rule #2).
- A task requires a secret/API key not yet in `docs/11_SECRETS_CHECKLIST.md`.
- Two documents genuinely conflict and you can't tell which is stale.
- A legal/regulatory citation can't be verified and the task requires printing it on user-facing output.
- You're about to introduce a new tool/service and you're not fully sure it satisfies the free-tier rule.

Do **not** stop and ask for things you can reasonably decide yourself and log (naming conventions, minor library choices already implied by the tech spec, code organization within an already-decided architecture).