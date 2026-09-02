# 05_DESIGN — Design System & the Stitch Hand-off Rule

## Read this file before you write a single line of UI code.

---

## 1. The rule (non-negotiable — this is why this file exists)

**The user generates all real screen designs in their own Google Stitch account, connected to the IDE via the Stitch MCP server. The coding agent must never invent, wireframe, or hand-build its own visual frontend design.**

Concretely, this means:
- Do **not** decide layout, visual hierarchy, color choices, spacing, or component composition from your own judgment.
- Do **not** ship a "placeholder" or "temporary" UI and call the task done — a placeholder UI has a way of becoming the permanent one under time pressure, and that is exactly the kind of silent drift this whole documentation system exists to prevent.
- When implementation reaches the point of needing an actual screen (Officer capture screen, Results/evidence screen, Review queue, Supervisor dashboard, Admin panel, etc.), **stop and explicitly tell the user**: *"This is a frontend/UI task — please generate the [screen name] design in Stitch and share the export so I can build against it."*
- Once the user provides a Stitch export (design spec, exported markup/assets, or a description of the generated design), build the real component against **that**, matching layout, spacing, and visual treatment as closely as the target framework (Next.js + Tailwind, per `03_TECHSPEC.md`) allows.
- If a Stitch export is genuinely incomplete for a specific interaction state (e.g., it shows the happy path but not the "offline / pending sync" state), ask the user rather than inventing the missing state's look yourself — log the gap in `10_OPEN_QUESTIONS.md` if it blocks progress.

**Why this rule exists, stated once so it doesn't need repeating elsewhere:** the user explicitly does not want an AI agent building its own frontend aesthetic for this project — Stitch is the design tool of record. This rule is restated in `AGENTS.md` and `12_GUARDRAILS.md` because it's the single most likely place for an agent to quietly drift off track by "being helpful" and just building a reasonable-looking screen instead of stopping to ask.

---

## 2. What the agent *can* decide without stopping

These are implementation details, not design decisions, and don't require a Stitch round-trip:
- Component file organization and naming.
- State management approach for a given screen (as long as it matches `03_TECHSPEC.md`/`04_APPFLOW.md` behavior).
- Which Tailwind utility classes implement a spacing/color value **that Stitch already specified** — translating a design into code is fine; inventing a design is not.
- Accessibility attributes (alt text, ARIA roles, focus order) that don't change visual design.
- Loading/error states' *behavior* (per `04_APPFLOW.md`) even before their *look* is finalized in Stitch — you can wire the state machine ahead of the visuals, as long as you don't also invent the visuals.

## 3. Design constraints to hand to Stitch (give the user this context when asking them to design)

When prompting the user to generate a screen in Stitch, remind them (or include in your ask) of the constraints that screen needs to satisfy, pulled from the rest of the doc set — this makes their Stitch session faster and keeps the eventual build aligned:

| Constraint | Source | Why it matters for the design |
|---|---|---|
| Usable one-handed, outdoors, in bright sunlight | `MASTER_CONTENT.md` §8.1 | High contrast, large touch targets, minimal reliance on subtle color differences |
| Must clearly distinguish "AI-suggested" vs. "officer-confirmed" fields | `04_APPFLOW.md` §2 | Needs a visibly distinct state, not just a tooltip |
| Pass / Fail / Needs Review must be instantly scannable at a glance across many fields | `MASTER_CONTENT.md` §10.5 | A results screen with many declarations needs strong visual grouping by verdict |
| Calibrated vs. uncalibrated font measurement must be visually distinct | `MASTER_CONTENT.md` §9.4 | Don't let an estimate look as certain as a calibrated measurement |
| Offline/pending-sync state needs its own visible indicator | `04_APPFLOW.md` §6 | Officers need to trust the app isn't losing their work |
| Evidence viewer needs to show a bounding box over a zoomable/pannable source image | `MASTER_CONTENT.md` §10.6 | Core differentiator feature — needs real design attention, not an afterthought |
| Every generated report must carry the legal disclaimer, unmissably | `01_PRD.md` US-07 | Should be a fixed part of the report template's design, not optional |

## 4. Screens known to be needed (ask Stitch to design these, in roughly this order, matching `07_IMPLEMENTATION_PLAN.md`)

1. Login (Officer/Admin)
2. Home / new inspection start
3. Capture (camera + multi-image + quality-gate feedback)
4. Processing / loading state
5. Results (per-declaration verdict list + evidence viewer)
6. Review queue (individual field confirm/correct)
7. Report preview/share
8. Search & history (past inspections)
9. Supervisor dashboard (trends, hotspots)
10. Admin panel (user management, rule-pack management)

This list is a build-order hint, not a rigid contract — if `07_IMPLEMENTATION_PLAN.md` sequences screens differently, follow that instead and update this list to match.

## 5. When the agent should proactively flag a design gap

If you notice a needed *state* of a screen has no design yet (e.g., the "empty search results" state, or the "rule pack validation failed" error state), don't invent it — tell the user specifically which state is missing, referencing the screen and the flow step from `04_APPFLOW.md`, and ask them to add it in Stitch. A specific ask ("the Admin rule-pack upload screen needs an error state for a failed schema validation, showing the specific validation message") is far more useful to the user than a generic "please design the rest."
