# 00_README — Documentation Map (NiyamDrishti — SIH26034 Legal Metrology Compliance Platform)

This folder is the project's operating manual. It exists so that any person or AI agent picking up this project — cold, mid-task, or after a context reset — can get fully oriented from files alone, without you having to re-explain the project from scratch again.

**Start here if you're a human:** read this file, then `../MASTER_CONTENT.md` once, then skim whichever numbered doc below matches what you're about to do.

**Start here if you're an AI coding agent:** you should have already read `../AGENTS.md`. If you haven't, stop and go read it now — it has your reading order and rules.

---

## The 15 files in this folder, in one line each

| # | File | Purpose |
|---|---|---|
| 00 | `00_README.md` | This file — the map. |
| 01 | `01_PRD.md` | Product Requirements Document — goals, personas, user stories, functional & non-functional requirements, explicit out-of-scope list. |
| 02 | `02_ROADMAP.md` | Phase-by-phase roadmap with milestones. High-level "when," not granular "how." |
| 03 | `03_TECHSPEC.md` | The full technical specification — architecture, verified free-tier tech stack, API surface, data flow, non-functional requirements, deployment. |
| 04 | `04_APPFLOW.md` | Screen-by-screen / step-by-step flow for every persona and every major user journey, including edge cases. |
| 05 | `05_DESIGN.md` | Design system guidance **and the mandatory Stitch MCP hand-off rule** — read before building any UI. |
| 06 | `06_SCHEMA.md` | Full database schema (tables, columns, relationships, indices) and the rule-pack JSON schema. |
| 07 | `07_IMPLEMENTATION_PLAN.md` | The granular, sequenced, checkable build plan. Every task has a stable ID. |
| 08 | `08_TRACKER.md` | Live status of every task in `07`. Must always have 1:1 task-ID parity with it — this is the anti-drift mechanism that was missing last time. |
| 09 | `09_DECISIONS.md` | Architecture Decision Records — a dated log of real technical choices and why they were made. |
| 10 | `10_OPEN_QUESTIONS.md` | Every unresolved ambiguity, conflicting source, or unverified fact found during research or build — with a resolution status. |
| 11 | `11_SECRETS_CHECKLIST.md` | Every API key / secret / env var the project needs, where to get it for free, and how to store it safely. |
| 12 | `12_GUARDRAILS.md` | The anti-drift rulebook for AI agents. The single most important file for keeping a coding agent on track. |
| 13 | `13_RECOVERY.md` | What to do when an agent (or a human) gets lost, a session resets, or work needs to be picked up mid-stream. |
| 14 | `14_TRANSLATION_AUDIT.md` | Periodic audit that what's actually been *built* still matches what the spec *asked for* — catches silent drift before it compounds. |
| — | `CHANGELOG.md` | Dated log of what has actually shipped. |

---

## How these files relate to each other

```
MASTER_CONTENT.md  (what the project IS — the anchor)
        │
        ├── 01_PRD.md          (what to build, formally)
        ├── 02_ROADMAP.md      (when, at a phase level)
        ├── 03_TECHSPEC.md     (how, technically)
        ├── 04_APPFLOW.md      (how it feels to use)
        ├── 05_DESIGN.md       (how it looks — via Stitch, not the agent)
        └── 06_SCHEMA.md       (how data is shaped)
                │
                ▼
        07_IMPLEMENTATION_PLAN.md  (the actual, granular build tasks)
                │
                ▼  (must always match 1:1)
        08_TRACKER.md              (status of each task)

09_DECISIONS.md, 10_OPEN_QUESTIONS.md, CHANGELOG.md  — running logs, updated continuously as work happens
11_SECRETS_CHECKLIST.md — reference, checked whenever a task needs a credential
12_GUARDRAILS.md, 13_RECOVERY.md, 14_TRANSLATION_AUDIT.md — process/safety nets, not project content
```

## The one rule worth repeating here

The original failure that led to this whole documentation system: the roadmap described everything, but the tracker — the file the agent was actually told to check before moving on — didn't contain everything the roadmap did. So the agent kept going, technically "checking the tracker," while real scope silently never got built.

The fix baked into this doc set: **`08_TRACKER.md` is not an independent file — it is a generated, 1:1 mirror of the task list in `07_IMPLEMENTATION_PLAN.md`.** Anyone (human or agent) editing one must edit the other in the same pass. See `12_GUARDRAILS.md` §"Tracker/Plan parity" for the enforced procedure.