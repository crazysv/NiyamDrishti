# MASTER CONTENT — NiyamDrishti (SIH26034 Legal Metrology Label Compliance Platform)

> **This is the single source of truth for what the project *is*.** Every other document in this repo (PRD, Tech Spec, Roadmap, Schema, etc.) is a *derived view* of this file for a specific purpose. If any other document ever seems to contradict this one, this file wins unless `docs/09_DECISIONS.md` records a later, explicit decision that supersedes it — see `docs/12_GUARDRAILS.md` for the full precedence order.
>
> Compiled from: (a) eight independent AI research passes on Problem Statement SIH26034 (uploaded by the user, cross-read in full), and (b) independent web research done in this session to verify every "free tool" and "current version" claim as of **September 2026**. Where sources disagreed, both positions are recorded and the disagreement is logged in `docs/10_OPEN_QUESTIONS.md` rather than silently picked.

---

## 0. How To Use This Document

- **New to the project?** Read this file top to bottom once. It's long by design — it's meant to replace re-explaining the project in every new chat.
- **An AI coding agent?** Do not skip this file. Read `AGENTS.md` first (it tells you the reading order and rules), then this file, then whichever numbered doc your current task needs.
- **Looking for a specific thing?** Jump to: [Regulatory Framework](#4-regulatory-framework-the-legal-core) · [Tech Stack](#11-technology-stack-100-free-tier-verified-sept-2026) · [Features](#10-feature-specifications) · [Schema overview](#12-database--rule-pack-schema-overview) · [Roadmap](#13-implementation-roadmap-overview)

---

## 1. Executive Summary

**Project Name:** NiyamDrishti
**Problem Statement ID:** SIH26034
**Title:** *"Software System to check compliance of Packaged Commodities under Legal Metrology (Packaged Commodities) Rules, 2011 by scanning products, images and labels."*
**Category:** Software
**Theme:** Agriculture, FoodTech & Rural Development (site theme) / Miscellaneous
**Organization / Sponsor:** Ministry of Consumer Affairs, Food & Public Distribution — Department of Consumer Affairs (DoCA)
**Submission deadline:** 20 September 2026 (Smart India Hackathon 2026)

**One-sentence pitch:** An offline-capable, inspector-first tool that turns a photo of a packaged product's label into an instant, evidence-backed, rule-by-rule compliance report against the Legal Metrology (Packaged Commodities) Rules, 2011 — replacing manual rulebook-flipping with a versioned, explainable rules engine that keeps every finding traceable back to the exact pixels that produced it.

**Core value proposition:** Legal Metrology Officers (LMOs) currently check packages by manually comparing physical labels against a dense, frequently-amended rulebook. This does not scale — coverage is a tiny fraction of the market, checks are slow (10–15 minutes each), and results are inconsistent between officers. This project automates extraction of every mandatory declaration from a label photo, validates each one against a versioned rules engine, and produces a report an officer can trust and a court could accept — because every flagged violation is linked back to a bounding box on the original image, not just an assertion.

**Key differentiators** (see §6 Competitive Landscape for the full comparison):
1. **Inspector-first**, not brand/artwork-first — built for field enforcement, not pre-print QA.
2. **Visual evidence mapping** — every extracted field and every violation is tied to an exact bounding box on the source image.
3. **Versioned rule engine** — regulatory amendments are data changes (JSON), not code changes.
4. **Offline-first** — designed to work in bazaars and rural areas with unreliable connectivity, syncing when back online.
5. **100% free/open-source core stack** — no vendor lock-in, no licensing cost, verified against August/September 2026 free-tier terms (see §11).
6. **Decision-support, not decision-maker** — every low-confidence or ambiguous field routes to a human review queue; the officer always has final authority, which is also the answer to the biggest legal-liability risk (§14).

---

## 2. The Official Problem Statement, In Full

Reproduced here (not paraphrased) because every downstream document depends on it word-for-word.

> **Background:** Packaged commodities are widely sold through retail stores, supermarkets and e-commerce platforms across India. Under the Legal Metrology Act, 2009 and the Legal Metrology (Packaged Commodities) Rules, 2011, every packaged commodity is required to bear mandatory declarations such as name and address of manufacturer/packer/importer, net quantity, Maximum Retail Price (MRP), month and year of manufacture/packing/import, consumer care details and other prescribed declarations in a specified format.
>
> **What They're Asking For:** Develop a software application capable of scanning packaged commodity labels, product images and product information to automatically assess compliance with the Legal Metrology (Packaged Commodities) Rules, 2011. The system should be capable of:
> - Scanning and analyzing images of packaged commodities.
> - Detecting mandatory declarations prescribed under Legal Metrology rules.
> - Checking correctness, completeness and placement of declarations.
> - Identifying missing or non-compliant declarations.
> - Checking readability and font size requirements.
> - Generating compliance reports and violation summaries.
> - Maintaining a repository of scanned products and compliance history.
> - Providing dashboards for enforcement officials.
>
> **Expected Solution, Key Points:**
> - User-friendly web and/or mobile-based software application.
> - Automated extraction and validation of mandatory declarations.
> - Rule-based compliance checking for Legal Metrology (Packaged Commodities) Rules, 2011.
> - Generation of digital compliance reports in PDF and editable formats.
> - Dashboard for monitoring inspections, violations and product compliance details.
> - Search and retrieval facility for previously scanned products and reports.
> - Technical documentation describing software architecture and deployment framework.
> - Image upload and product scanning functionality.

**Independent scoring found in the source material** (from an automated SIH problem-statement evaluator, included here for planning context, not as a requirement):
- Innovation: Moderate — one clear modern-tech core (AI/CV) applied to a real workflow.
- Effort: Medium (score 8/10) — 8 distinct asks in the official text; achievable in 36 hours with a focused team and a clear build order.
- Competitive crowding: Medium — 3 of 226 live SIH 2026 problem statements ask for a genuinely similar build; 12 PS share the "Agriculture, FoodTech & Rural Development" theme.
- Architecture flag: "Complex Integration" — a 3-layer stack (data/integration → core logic/AI → dashboard/app), most bugs show up at the seams between layers, not inside them.
- What evaluators will likely ask: where the training/test data comes from (real vs. synthetic), what the AI component does that a simpler rule-based system couldn't, what happens when connectivity/hardware/data fails, how it holds up at production scale, and who benefits and how that's measured post-deployment.

---

## 3. Problem Deep Dive

### 3.1 Why this matters
Accurate labels are the only information a shopper actually has at the point of sale — quantity, price, ingredients, safety warnings. Non-compliant labels (missing MRP, incorrect net quantity, illegible font, no manufacturer address) cause direct financial harm to consumers and give non-compliant sellers an unfair advantage over compliant ones. For rural sellers and small packers, a system that helps them self-check *before* a formal inspection is also a market-access tool, not just an enforcement one.

### 3.2 Why manual inspection doesn't scale
- An officer physically compares a label against a printed/memorized rulebook — 10–15 minutes per product, subjective, and dependent on individual officer knowledge of the latest amendments.
- Coverage today is a small fraction of the packaged-goods market; the bottleneck is entirely human throughput, not legal authority.
- Errors and inconsistency between officers are inevitable at this scale, and there is no structured evidence trail — findings are usually handwritten notes, not reproducible records.

### 3.3 The regulatory pain point specific to this domain
The rules themselves are not static. Amendments arrive piecemeal (see §4.5) and a paper-based or hard-coded system goes stale the moment a rule changes. Any credible solution must treat "what the rule says today" as **versioned data**, not as logic buried in application code — this single architectural choice is what separates a real enforcement tool from a hackathon toy that breaks on the next gazette notification.

### 3.4 The eMaap finding (read this carefully — it is a live open question)
Sources disagree here, and the disagreement matters for how you pitch the project:
- **Earlier-round research** claimed the government's **eMaap** portal (the National Legal Metrology system) has *no* image-scanning, OCR, or field-level violation detection — i.e., a total gap this project fills.
- **Later-round, more careful research** found that eMaap's *published materials* indicate it **does** cover some enforcement functions (licensing, registration, verification workflows) — so "eMaap has zero enforcement" is **not accurate** as a blanket claim.
- **The defensible, corrected position** (used throughout this document): eMaap is a licensing/registration/business-verification portal. There is no public evidence it does **package-level image inspection, OCR-based declaration extraction, font/legibility measurement, or bounding-box evidence generation**. This project's honest pitch is: *"We are not rebuilding eMaap. We are the image-evidence/inspection-intelligence layer eMaap does not have, and we're built to feed structured violation data into it (or a similar system) via API."* Do not claim eMaap "has no enforcement" in a demo — a judge who has read the DoCA site will call this out. This exact wording distinction is logged as Open Question OQ-01.

### 3.5 Who benefits
- **Legal Metrology Officers** — drastically reduced inspection time, structured evidence instead of notes, defensible records.
- **Consumers** — better-enforced accurate labeling, protection from underweight/mispriced goods.
- **Compliant manufacturers/packers** — a level playing field; large or small, everyone is checked against the same versioned rules.
- **Rural/small packers (self-check use case)** — a free tool to verify their own labels before going to market, reducing accidental non-compliance from packers who simply don't have legal counsel on staff.

---

## 4. Regulatory Framework (the legal core)

> **Read this section like code, not prose.** Every number here drives a rule in the rules engine (`docs/06_SCHEMA.md` §"Rule Pack Schema"). Where two sources in the research disagreed on an exact clause letter, both are shown and the item is flagged **[VERIFY]** — the agent must not silently pick one when implementing; log it in `docs/10_OPEN_QUESTIONS.md` and confirm the exact clause against the bare act / an official gazette copy before hard-coding it into a rule pack, since a wrong clause citation on an inspection report is a real legal-credibility risk.

### 4.1 Governing legislation
- **Legal Metrology Act, 2009** — the parent Act.
- **Legal Metrology (Packaged Commodities) Rules, 2011 ("LMPC Rules")** — the operative rules this entire project validates against.
- **Legal Metrology (General) Rules, 2011** — companion rules (weighing/measuring instruments — largely out of scope for this project, which focuses on packaging declarations).
- Multiple **amendments** since 2011, most relevantly a cluster of 2025–2026 amendments (§4.5).

### 4.2 Mandatory declarations (Rule 6) — the checklist the whole product is built around
Every pre-packaged commodity intended for retail sale must declare, on the package itself:

| # | Declaration | Typical extraction target | Notes |
|---|---|---|---|
| 1 | Name and address of manufacturer / packer / importer | Text block | Multiple entities possible (manufactured-for vs. marketed-by) |
| 2 | Common / generic name of the commodity | Text | |
| 3 | Net quantity (weight/volume/number) | Number + unit | Must be in standard (metric) units |
| 4 | Month & year of manufacture / packing / import | Date | Format varies by commodity |
| 5 | Maximum Retail Price (MRP) — inclusive of all taxes | Currency value | The single most litigated declaration; **[VERIFY exact sub-clause letter — sources cite it variously as Rule 6(1)(d) and Rule 6(1)(f); confirm against the bare act before coding]** |
| 6 | Consumer care / customer-care details (address, phone, email) | Text block | |
| 7 | Country of origin (for imported goods, and for e-commerce listings post-2020/2026 amendments) | Text | See §4.5 |
| 8 | Dimensions/number of the commodity, where applicable (e.g. count of items) | Number | |
| 9 | Best-before / use-by / expiry date, where the commodity type requires it | Date | Food, pharma, cosmetics |

Some source drafts group these as Rule 6(1)(a) through (g)/(h); others use different lettering. **Do not hard-code a specific sub-clause letter into a rule pack's user-facing report text without verifying it against a primary source** — a citation error is worse than no citation on an official-facing report. Cite the **rule number and the plain-English requirement**, not the sub-clause letter, unless verified.

### 4.3 Font size & legibility requirements (Rule 7 / Rule 6(10A) area)
This is the most technically interesting rule to implement, because it requires **converting pixels to physical millimeters** — see §9.4 for the calibration technique. The size thresholds scale with the Principal Display Panel (PDP) area:

| Principal Display Panel (PDP) area | Minimum declaration font height |
|---|---|
| ≤ 50 cm² | 1.0 mm |
| ≤ 100 cm² | 1.5 mm |
| ≤ 500 cm² | 2.0 mm |
| ≤ 2500 cm² | 4.0 mm |
| > 2500 cm² | 6.0 mm |

Separate/adjusted thresholds exist for **blown, formed, embossed, or perforated containers** (e.g., glass bottles where text is molded rather than printed) — treat these as a distinct rule variant in the rule pack, not the same threshold table, and confirm exact figures against the bare act before launch **[VERIFY]**.

### 4.4 Exemptions
- Rule 26 and the Second Schedule carve out categories exempt from some/all declaration requirements (e.g., certain agricultural produce sold loose, specific small-pack categories under specific conditions). Historically, very small packs (e.g., ≤10g/10ml for some categories) had lighter requirements — **this has been actively narrowed by 2025–2026 amendments for specific product categories (notably pan masala — see §4.5)**, so do not assume an old exemption still applies without checking the rule pack's effective date against the package's likely manufacture date.

### 4.5 Key 2025–2026 amendments (why the rule engine MUST be versioned, not hard-coded)

| Amendment | Effective / notified | What changed |
|---|---|---|
| **Legal Metrology (Packaged Commodities) Second Amendment Rules, 2025** | Effective **1 February 2026** | Mandatory **Retail Sale Price (RSP) display on pan masala packs**; **removes the small-pack exemption** that previously let very small pan masala packs skip RSP declaration (G.S.R. 881(E)) |
| **E-commerce Country-of-Origin amendment** | 2026 | Country-of-origin declaration requirements extended/clarified for goods sold via e-commerce listings, not just physical packages |
| **Legal Metrology (Packaged Commodities) Third Amendment Rules, 2026** | Notified **May 2026** | Adjustments including AEO Tier-2/Tier-3 bonded-warehouse flexibility and increased director/officer accountability language |
| **Legal Metrology (Government Approved Test Centre) Amendment Rules, 2026** | 2026 | Changes to how test centres are approved/accredited (indirect relevance — affects who can issue certain compliance certificates) |
| Medical-device package declarations | Ongoing | Medical-device packaging follows **Medical Devices Rules, 2017** for some declarations/fonts rather than the general LMPC table — treat as a distinct commodity-category rule variant |

**Design implication:** every rule the engine checks must carry an `effective_from` (and optionally `effective_to`) date and a `source_citation` field. A rule pack is a **dated snapshot**; the engine picks the rule pack version applicable at inspection time (or lets the officer pick, for training/what-if use). This is what "amendment-proof" means in practice — see the rule-pack JSON shape in §12.2.

### 4.6 Penalties (for report language, not for the engine to "decide")
Indicative penalty figures found in the research (confirm against the Act/current gazette before printing on any official-looking report): **₹25,000 for a first offense**, escalating (commonly cited around **₹1,00,000** for subsequent offenses) under the Legal Metrology Act's penalty provisions. The system should **cite** the relevant penalty section for context on a report, but must **never present itself as issuing a penalty or a legal verdict** — see §7 "what we are NOT building."

### 4.7 Regulatory bodies referenced across sources (use with care)
- **Department of Consumer Affairs (DoCA)** — the sponsoring ministry; the actual regulatory home of Legal Metrology enforcement.
- **eMaap** — DoCA's national Legal Metrology portal (see §3.4 — licensing/registration/verification, not package-image inspection).
- One earlier-round source associated **DGQA (Directorate General of Quality Assurance)** and **BIS (Bureau of Indian Standards)** with this domain — **this is likely an inaccurate association** (DGQA is a Ministry of Defence quality body; BIS does relevant standards work but is a separate regulatory track from Legal Metrology). **Do not cite DGQA in a pitch or report** — flagged as Open Question OQ-02 / treat as a research error to avoid repeating, not as project fact.

---

## 5. Existing Government Infrastructure — What We Integrate With vs. Replace

| System | What it actually is | Our relationship to it |
|---|---|---|
| **eMaap** | National Legal Metrology licensing/registration/verification portal | We do not replace it. Phase 2+ target: push structured violation JSON to it via a REST adapter (aspirational — no confirmed public API as of this research; treat as Phase 3, not MVP) |
| **Bhashini (ULCA)** | MeitY's free national speech/translation platform (22 scheduled languages) | Phase 2 target for vernacular voice UI / Indic-language OCR assist — free for developer/individual use per ULCA sign-up, confirmed independently (see §11.11). Not an MVP dependency — deferred specifically because government API approval timelines are unpredictable and must never block a hackathon or MVP deadline |
| **MeriPehchan / Jan Parichay** | Government SSO (National Single Sign-On) | Phase 2/3 target for officer login instead of self-rolled auth, once the team wants government-grade identity |
| **UMANG** | Government citizen app platform | Phase 3 aspirational — consumer-facing "scan your own purchase" mode |
| **DigiLocker** | Government document wallet | Phase 3 aspirational — signed/verifiable copies of inspection certificates |

**Rule for the agent:** none of the Phase 2/3 government integrations above are MVP requirements. Do not attempt to wire any of them up unless the current task in `docs/07_IMPLEMENTATION_PLAN.md` explicitly says so — most require an approval process outside this project's control and must never block core delivery.

---

## 6. Competitive Landscape

### 6.1 Direct/adjacent competitors found in research

| Competitor | Type | Focus | Gap vs. this project |
|---|---|---|---|
| **LabelLens** (GH Raisoni Skill Tech University, prior SIH cohort) | Prior hackathon project on the *same* problem statement family | Scans label photos, OCR + rule-based validation, explanatory feedback, monthly reporting, manual review workflow | The most direct benchmark to beat — good baseline feature set (explanatory feedback, review workflow) but nothing indicates visual evidence bounding boxes, offline-first design, or a versioned rule engine. Differentiate by going deeper on these three. |
| **Product Label Guru** | Commercial SaaS | Brand/manufacturer-side pre-print artwork compliance (FSSAI/BIS/Legal Metrology) | Built for brand legal teams validating **pre-print PDF artwork**, not photos of physical retail packages in the field; no inspector workflow |
| **Seventeen29** | Commercial SaaS | AI packaging compliance / artwork management | Same pre-launch/brand-workflow focus as above |
| **GlobalVision** | Commercial | Packaging QA (text/graphics/barcode inspection) | Commercial packaging-industry workflow, not government field enforcement |
| **MetaMark** | Open-source (GitHub) | Automated compliance checking / vision AI for e-commerce | Research-grade, not production/offline-ready |
| **eMaap Portal** | Government | Licensing, registration, certification | High-level business verification, not package-image inspection (see §3.4/§5) |

### 6.2 What none of them have (our differentiation set)
- Inspector-first workflow designed for government field enforcement (not brand QA).
- Visual evidence mapping — every finding traceable to an exact bounding box.
- A versioned rule engine that survives regulatory amendments without a code deploy.
- True offline-first operation for low-connectivity field conditions.
- Physical-package ↔ e-commerce-listing cross-consistency checking.
- A 100% free/open-source core stack with no vendor lock-in.
- An enforcement-grade, tamper-evident audit trail structured for potential legal/evidentiary use.

### 6.3 Manual inspection as the "real" incumbent
The actual competitor most of the time is not another product — it's a human with a printed rulebook. That comparison (speed, consistency, coverage, evidence quality) is the strongest part of the pitch and should anchor any demo narrative.

---

## 7. Product Vision & Differentiation

### 7.1 What we ARE building
A **decision-support tool** for Legal Metrology field enforcement: photograph a package (or multiple angles/sides), get back structured extracted declarations, a per-declaration pass/fail/needs-review verdict tied to the specific rule and the specific pixels that produced the finding, and a generated inspection report.

### 7.2 What we are explicitly NOT building
- **Not** a legal-verdict engine — it never issues a penalty or a legally binding ruling. It surfaces findings; a human officer decides.
- **Not** a pre-print brand/artwork QA tool (that's Product Label Guru's job).
- **Not** a replacement for eMaap (see §3.4/§5).
- **Not**, in the MVP, a consumer-facing app — this is an officer/enforcement tool first (a consumer "check before you buy" mode is a legitimate Phase 3 idea, not a Phase 1 distraction).
- **Not** dependent on any paid API, government approval, or custom domain to run its core, demoable feature set — see §11 "Guardrails" for why this constraint exists.

### 7.3 The memorable one-line judge pitch
*"We didn't rebuild eMaap — we built the missing evidence layer under it: point a phone at a label, and get back a rule-by-rule, pixel-traceable compliance report in seconds instead of a 15-minute manual check."*

---

## 8. User Personas & Workflows

### 8.1 Primary: Legal Metrology Officer / Inspector (field user)
- **Context:** In a market, warehouse, or retail store, often with patchy connectivity, sometimes handling many products per visit.
- **Core workflow:** Open app → capture package (front + back + any side panels needed) → app preprocesses & runs OCR → extracted declarations shown with confidence scores → violations highlighted with evidence → officer reviews/overrides low-confidence fields → generate report → (sync when online).
- **Needs:** speed, offline reliability, large touch targets usable one-handed/outdoors in bright light, zero ambiguity about what's "AI-suggested" vs. "officer-confirmed."

### 8.2 Secondary: Enforcement Supervisor
- **Context:** Reviews a team's inspection history, spots compliance trends/hotspots, may need to escalate patterns of violation by a specific manufacturer.
- **Core workflow:** Dashboard → filter by officer/date/region/violation type → drill into individual inspections → export summaries.

### 8.3 Tertiary: Department Administrator
- **Context:** Manages officer accounts, manages rule-pack versions/updates, oversees system-wide analytics.
- **Core workflow:** User management → rule-pack version management (upload/activate a new amendment's rule pack) → system-wide analytics/exports.

### 8.4 Future persona: Manufacturer/Packer/Importer (self-check, Phase 3+)
- **Context:** Wants to verify their own label is compliant before it goes to market.
- **Core workflow:** Same capture/extraction/validation pipeline, but framed as a self-check tool rather than an enforcement action; no violation gets logged against them in the enforcement database — this must be a **structurally separate mode**, not a checkbox, to avoid any confusion between "I checked my own label" and "an officer inspected my product."

---

## 9. Technical Architecture

### 9.1 System overview (3-layer, as the official evaluator flagged)
```
┌───────────────────────────────────────────────────────────────┐
│  CLIENT LAYER  (PWA — installable, offline-capable)            │
│  Capture UI · Image quality checks · Offline queue (IndexedDB) │
│  · (optionally) client-side OCR inference                      │
└───────────────────────────────────┬─────────────────────────────┘
                                     │ sync when online
┌───────────────────────────────────▼─────────────────────────────┐
│  API LAYER  (FastAPI)                                           │
│  Auth · Upload handling · OCR orchestration · Rule engine       │
│  · Evidence mapping · Report generation · Review-queue logic    │
└───────────────┬───────────────────────────────────┬─────────────┘
                │                                   │
┌───────────────▼───────────────┐   ┌───────────────▼─────────────┐
│  DATA LAYER                   │   │  OBJECT STORAGE              │
│  Postgres (Neon) — structured │   │  Cloudflare R2 — images,     │
│  inspections, users, rules,   │   │  generated PDF reports        │
│  audit log                    │   │                               │
└────────────────────────────────┘   └───────────────────────────────┘
```
Most integration bugs, per the official evaluator's own risk note, show up **at the seams between these layers** — budget real implementation time for the client↔API sync contract and the API↔storage contract, not just for building each layer in isolation. This directly informs the task ordering in `docs/07_IMPLEMENTATION_PLAN.md` (integration spikes happen early, not "at the end").

### 9.2 Core intelligence pipeline (per inspection)
1. **Capture** — one or more images (front PDP, back panel, any side needed for a specific declaration).
2. **Quality gate** — blur/glare/lighting/perspective/crop/resolution/occlusion checks; reject or warn *before* wasting an OCR pass on an unusable image.
3. **Preprocessing** — resize, denoise, contrast adjust, perspective-correct, deskew, optional glare suppression.
4. **OCR + layout extraction** — text + bounding box + confidence per detected text region (see §11.3 for the OCR engine decision).
5. **Declaration extraction** — structured field extraction from raw OCR output (regex/heuristics + optionally a lightweight classifier) into typed fields: `mrp`, `net_quantity`, `manufacturer_address`, `mfg_date`, `consumer_care`, `country_of_origin`, etc. Every extracted field retains its source bounding box(es).
6. **Optical calibration** — establish a pixel→millimeter scale (see §9.4) so font-height rules can be checked, not just presence/absence.
7. **Rule engine evaluation** — run the active rule pack (§4.5/§12.2) against extracted fields → per-declaration verdict: **Pass / Fail / Needs Review**.
8. **Evidence mapping** — bind every verdict to the exact bounding box(es) that produced it, for the report and for officer review.
9. **Human review queue** — any field below a confidence threshold (baseline: 85%, tune during Phase 1 testing) is routed here; officer corrects/confirms; correction is logged to the immutable audit trail, never silently overwritten.
10. **Report generation** — PDF (and an editable format) summarizing pass/fail/review-needed per declaration, with evidence thumbnails.
11. **Storage & sync** — persist inspection, images, and report; if captured offline, queue and sync when connectivity returns.

### 9.3 Multi-image support
A single inspection can combine: front PDP photo, back/side panel photo(s), a secondary sticker image (common when MRP is corrected via sticker), and (Phase 2+) an e-commerce listing screenshot for cross-consistency checking. The system combines these into **one inspection context** with cross-image declaration matching (e.g., does the MRP on the sticker match the MRP printed on the e-commerce listing?).

### 9.4 The barcode calibration trick (why this project can measure *physical* millimeters from a photo)
You cannot know true font height in millimeters from a phone photo alone — pixel size depends on distance and camera. The fix used across the strongest sources: **EAN-13 barcodes have a fixed, globally standardized nominal width (37.29 mm)**. If a barcode is visible in the image, measure its pixel width, derive a `mm-per-pixel` scale factor from that known physical width, and apply that scale to measure font height elsewhere on the same image. If no barcode is visible, **fall back to a relative PDP-height-ratio estimate and flag the measurement as "Uncalibrated"** rather than asserting false precision — this distinction (calibrated vs. uncalibrated measurement) must be visibly shown on the report, never silently defaulted.

### 9.5 Offline-first design
- Client queues captures + metadata in IndexedDB when offline.
- Sync is incremental and resumable, not "all or nothing."
- If client-side OCR is used (see §11.3 decision), the officer can get provisional results even fully offline; server-side re-validation happens on sync.
- Local storage is capacity-bounded (compress images, cap queue depth, warn before the device runs out of space) — this is a named risk in §14.

---

## 10. Feature Specifications

### 10.1 Capture Module
- Mobile camera capture (PWA `getUserMedia`/`react-webcam`), drag-and-drop upload, multi-image per inspection, optional manual metadata entry (commodity category, if known — helps the rule engine pick category-specific rules like the pan-masala RSP rule).
- **Quality checks before OCR runs:** blur detection, poor-lighting detection, glare detection, extreme-perspective detection, crop-error detection, low-resolution detection, excessive-darkness detection, "text too small to be useful" detection, severe-occlusion detection. Each should give the officer a specific, actionable retake reason — not a generic "bad photo" message.

### 10.2 Image Preprocessing
Resize → noise reduction → contrast adjustment → perspective correction → deskew → optional glare suppression → text-region enhancement → OCR-ready output. (OpenCV + Pillow; see §11.4.)

### 10.3 OCR + Layout Extraction
Every OCR result retains: extracted text, confidence score, bounding-box coordinates, and source-image reference — this is the foundation the entire evidence-mapping feature depends on; do not use an OCR path that discards bounding boxes, even if it's marginally more accurate on text alone.

### 10.4 Declaration Extraction
Transforms raw OCR text + boxes into typed, structured fields. Example shape:
```json
{
  "field_type": "mrp",
  "raw_text": "MRP: ₹149.00 (Incl. of all taxes)",
  "parsed_value": 149.00,
  "currency": "INR",
  "confidence": 0.94,
  "bounding_box": {"x": 120, "y": 340, "w": 210, "h": 38},
  "source_image_id": "img_002"
}
```

### 10.5 Regulatory Rule Engine
Loads the **active rule pack** (versioned JSON, §12.2), evaluates each extracted field against the relevant rule(s), and produces a verdict per declaration: `pass`, `fail`, or `needs_review` (used when confidence is below threshold or the field wasn't found but might legitimately be exempt). Rule logic is **decoupled from application code** — an amendment is a new/edited rule-pack entry, never a code change (§4.5).

### 10.6 Evidence Mapping
Binds every field and every violation to its source bounding box(es) for the report UI and for officer review — the core differentiator vs. every competitor in §6.

### 10.7 Compliance Validation
Aggregates per-declaration verdicts into an overall inspection status; supports commodity-category-specific rule variants (e.g., pan masala's RSP rule, medical-device font rules under the separate 2017 Rules).

### 10.8 Human Review Workflow
Fields below the confidence threshold are queued for officer review; the officer can accept, correct, or override any field. Every override is written to the **immutable audit log** (who, when, what changed, before/after value) — never a silent overwrite.

### 10.9 Inspection Report Generation
PDF (WeasyPrint, §11.6) and an editable format, containing: per-declaration verdicts, evidence thumbnails with highlighted bounding boxes, cited rule/section per finding (using verified citations only — §4.2/§4.6), officer sign-off, and a clear "AI-assisted decision support, not a legal ruling" disclaimer (this disclaimer is a **product requirement**, not boilerplate — see §14.2 regulatory risk mitigation).

### 10.10 Storage & History
Every inspection, its images, extracted fields, verdicts, and any officer overrides are retained with search/filter/retrieval by product, officer, date range, region, and violation type — a direct requirement from the official problem statement ("maintaining a repository of scanned products and compliance history").

### 10.11 Analytics Dashboard
Compliance trends, violation hotspots by category/region/manufacturer, officer activity/throughput, rule-pack version usage — a direct requirement from the official problem statement ("dashboards for enforcement officials").

### 10.12 E-Commerce Mode (Phase 2+)
Cross-checks a physical package's declarations against its online listing (same product, different channel) — flags mismatches (e.g., listing says 500g, physical package says 450g).

### 10.13 Advanced / Stretch Features (explicitly Phase 2+, not MVP)
- Bhashini-powered Indic-language voice UI for officers more comfortable in a regional language.
- Batch/warehouse scanning mode (many SKUs in one session).
- Manufacturer self-check portal (§8.4).
- Government-system integrations listed in §5.

---

## 11. Technology Stack — 100% Free-Tier-Verified (Sept 2026)

> **Non-negotiable constraint driving every choice below:** every component must be free, or have a genuinely usable free tier, with **no indirect paid dependency**. The canonical anti-pattern to avoid — found and explicitly corrected during this research — is **Resend**: its free email-sending tier is real, but production-grade deliverability effectively requires a **verified custom domain (DNS/SPF/DKIM/DMARC)**, and a domain is a recurring paid cost. A tool being "free" is not enough if using it *properly* silently requires something paid. Every recommendation below was checked against this trap. Where a tool has a real caveat (pauses on inactivity, needs a card for verification, etc.), the caveat is stated plainly rather than hidden.

### 11.1 Frontend

| Component | Tool | License | Why | Free-tier reality check (Sept 2026) |
|---|---|---|---|---|
| Framework | **Next.js 14+** (App Router) | MIT | PWA support, camera access, SSR/SSG flexibility, huge ecosystem | Free framework; hosting cost is separate (below) |
| UI | React + TypeScript | MIT | Type safety, ecosystem | Free |
| Styling | Tailwind CSS | MIT | Fast, consistent | Free |
| Icons | Lucide React | MIT | Modern, consistent | Free |
| Camera | react-webcam | MIT | Browser camera access | Free |
| Evidence viewer | react-zoom-pan-pinch | MIT | Zoom/pan for bounding-box evidence review | Free |
| PDF preview | react-pdf | MIT | Client-side PDF rendering | Free |
| Offline queue | Dexie.js (IndexedDB wrapper) | Apache 2.0 | Reliable offline storage/sync queue | Free |
| **Hosting** | **Cloudflare Pages** (primary) | — | Unlimited bandwidth on the free tier, pairs naturally with Cloudflare R2 for storage | Genuinely free, standing tier |
| Hosting (alt) | Vercel (Hobby) | — | Best-in-class Next.js DX | Free Hobby tier; fine for non-commercial/small-team use — confirm current Vercel Hobby terms before a production government rollout |

### 11.2 Backend

| Component | Tool | License | Why |
|---|---|---|---|
| Framework | **FastAPI** | MIT | Async, ideal for I/O-bound OCR/CV pipelines, auto-generated OpenAPI docs |
| Language | Python 3.11+ | PSF | Best OCR/CV ecosystem |
| Validation | Pydantic | MIT | Data validation/serialization |
| API docs | Swagger UI (built into FastAPI) | Apache 2.0 | Free |
| **Hosting** | **Render** (free Web Service) | — | Genuinely free, no card required, deploys from GitHub. **Caveat:** the free instance sleeps after a period of inactivity and cold-starts on the next request — mitigate by warming it up before a demo, and design the offline client so a cold start is invisible to the officer mid-inspection |
| Hosting (scale-up alt) | Google Cloud Run | — | True always-free request quota; **caveat:** GCP account setup typically requires adding a billing/card for identity verification even though usage under the free quota stays $0 — confirm this is acceptable before choosing it |
| Hosting (alt, ML-heavy) | Hugging Face Spaces (Docker) | — | Good fit for ML workloads; **caveat, actively flagged in research:** HF's free CPU tier has been in flux in 2026 (community reports of the free "CPU Basic" flavor being restricted in favor of paid/ZeroGPU tiers) — verify current terms at build time before depending on it for anything beyond experimentation |

### 11.3 OCR & Computer Vision — the key architectural decision

| Component | Tool | License | Why |
|---|---|---|---|
| Primary OCR | **PaddleOCR — PP-OCRv6** (tiny/small/medium tiers, 1.5M–34.5M params) | Apache 2.0 | Latest generation (released June 2026); medium tier beats PP-OCRv5_server by +5.1% recognition / +4.6% detection while being far smaller; ~5.2× CPU inference speedup with OpenVINO — specifically chosen because the **tiny/small tiers are light enough to be realistic on free-tier CPU hosting**, unlike older heavyweight OCR stacks |
| Fallback OCR | Tesseract 5.x | Apache 2.0 | Mature, CPU-friendly, zero setup complexity |
| Document/complex layout (Phase 2+) | PaddleOCR-VL 1.5 (0.9B VLM) | Apache 2.0 | 94.5% accuracy on OmniDocBench v1.5 (2026) — stronger structured-understanding option once the MVP pipeline is proven |
| Image processing | OpenCV (opencv-python) | Apache 2.0 | Preprocessing pipeline (§10.2) |
| Image handling | Pillow (PIL) | HPND | |
| Barcode/QR (for the mm calibration trick, §9.4) | pyzbar | MIT | |
| Barcode (alt) | ZXing (Python wrapper) | Apache 2.0 | |

**Open architecture decision — flagged for a Phase 1 spike, not pre-decided here (see `docs/09_DECISIONS.md` seed entry and `docs/10_OPEN_QUESTIONS.md` OQ-03):**
- **Option A — client-side OCR** (PaddleOCR.js / Tesseract.js running via WASM in the browser). Zero server RAM/CPU cost, works fully offline (directly satisfies §9.5), but real-world accuracy/speed on typical officer phones is unverified in this research and must be prototyped early.
- **Option B — server-side OCR** (Render/Cloud Run running PaddleOCR). Likely higher accuracy ceiling and easier to upgrade centrally, but consumes the constrained RAM/CPU of a free-tier host and can't work while the device is offline.
- **Recommended default to prototype first:** Option A for the capture-time provisional result (keeps the offline promise real), with an optional Option B server-side re-validation pass on sync, for the best of both — but this must be validated with a real spike task before committing, not assumed.

### 11.4 Database & Storage

| Use case | Tool | License | Why | Free-tier reality check |
|---|---|---|---|---|
| Primary DB | **Neon** (PostgreSQL) | PostgreSQL License | Permanent free tier, **no card required, no forced pause/expiry** (scale-to-zero ≠ data loss), commercial use allowed | Confirmed as one of the few genuinely permanent free Postgres tiers as of Aug 2026 |
| Alt DB (if you want Auth+Storage bundled) | Supabase | Apache 2.0 (core) | Full backend-in-a-box (DB + Auth + Storage + Realtime) | Free tier is real but **pauses after inactivity** (roughly a week) — acceptable for a hackathon/pilot, plan a "wake up" ping if chosen for anything demo-critical |
| Local/offline/dev fallback | SQLite | Public Domain | Zero-setup, file-based — good for local dev and fully offline demo mode | Free, no caveats |
| ORM | SQLAlchemy | MIT | Database-agnostic, async support | |
| Migrations | Alembic | MIT | Schema versioning | |
| **Object/file storage** | **Cloudflare R2** | — | S3-compatible; **10 GB storage / 1M write-class ops / 10M read-class ops free monthly, and — the actual reason it wins here — zero egress fees, permanently, at any tier** | Confirmed stable, no reported pricing changes as of Aug 2026 |
| Local storage fallback | Local filesystem | N/A | Dev/offline mode | Free |

### 11.5 Authentication & Security

| Component | Tool | License | Why |
|---|---|---|---|
| Auth | Self-rolled JWT via FastAPI (no vendor lock-in) | MIT stack (python-jose, passlib/bcrypt) | Officers/admins are provisioned accounts, not public signups — a full vendor auth platform is unnecessary complexity and an unneeded dependency; **government SSO (MeriPehchan/Jan Parichay) is a deliberate Phase 2/3 upgrade**, not a Phase 1 requirement |
| Rate limiting | slowapi | BSD | Free |
| CORS | FastAPI/Starlette built-ins | — | Free |

### 11.6 PDF / Report Generation

| Component | Tool | License | Why |
|---|---|---|---|
| Primary | **WeasyPrint** | BSD | HTML+CSS → PDF; best for report-style layouts with evidence-image embedding | Free, but has native system dependencies (Pango/Cairo) — confirm they install cleanly on the chosen host image before relying on it for the demo |
| Alt (lighter) | FPDF2 | MIT | Zero system-dependency alternative if WeasyPrint proves painful on the hosting target | Free |
| Alt (complex tables) | ReportLab (open-source edition) | BSD | Free |

### 11.7 Email / Notifications — the exact trap this project must avoid repeating

| Component | Tool | Why | The specific caveat |
|---|---|---|---|
| **Primary (recommended)** | **Gmail SMTP** (`smtp.gmail.com` + an App Password) | Completely free, **zero domain requirement**, entirely sufficient for a low-volume, internal officer-notification use case (password resets, "your report is ready" pings) | Google-account daily send caps apply (a few hundred/day) — plenty for MVP/pilot scale |
| Alt (scales further, still no domain needed to start) | Brevo (free tier, ~300 emails/day) | Free tier can send without your own verified domain (using Brevo's shared sending identity) | Deliverability improves with a verified domain later — optional upgrade, not a blocker |
| **Explicitly avoid as a default** | Resend / SendGrid-style providers | Their free API tiers are real, but production deliverability effectively requires a **verified custom domain (SPF/DKIM/DMARC)** | This is the exact "free tool, paid dependency" trap the project hit before — only use these if the team already owns a domain they're happy to configure |

### 11.8 Rule Engine
Pure Python, no dependency beyond the standard library + Pydantic for schema validation of the rule-pack JSON — deliberately zero third-party service dependency here, since this is the most legally sensitive part of the system.

### 11.9 DevOps & Deployment

| Component | Tool | License | Why |
|---|---|---|---|
| Containerization | Docker | Apache 2.0 | Consistent dev/prod parity |
| Local orchestration | Docker Compose | Apache 2.0 | Multi-container local dev |
| CI/CD | GitHub Actions | MIT (free minutes on public/limited private repos) | Automated test/deploy |
| Reverse proxy (if self-hosting later) | Nginx | BSD | Free |
| SSL (if self-hosting later) | Let's Encrypt / Certbot | Apache 2.0 | Free |
| Monitoring (optional, later) | Prometheus + Grafana | Apache 2.0 | Free, self-hostable |

### 11.10 Development Tooling

| Component | Tool | License |
|---|---|---|
| Python packaging | pip + poetry | MIT |
| Linting | Ruff | MIT |
| Formatting | Black | MIT |
| Type checking | mypy | MIT |
| Testing | pytest, pytest-cov | MIT |
| API test client | httpx | MIT |

### 11.11 Multilingual (Phase 2+)
**Bhashini (ULCA)** — MeitY's national language platform. Free for developer/individual use at low volume via sign-up at bhashini.gov.in; paid tiers only apply once you scale to production and monetize/charge end users. This is genuinely free at the scale this project needs, but it is a **government service with its own account-approval process outside this project's control** — hence deliberately placed in Phase 2, never on the MVP critical path.

### 11.12 Mobile Wrapper (Phase 3, optional)
**Capacitor** (MIT) — wraps the existing PWA as an installable Android/iOS app if an app-store presence is ever required, without maintaining a second native codebase. Not needed while the PWA meets field requirements.

### 11.13 Frontend Design Tooling — READ THIS BEFORE BUILDING ANY UI
The user generates actual screen designs in their own **Google Stitch** account, connected to the IDE via the **Stitch MCP server**. **The coding agent must not invent, wireframe, or hand-build its own frontend visual design.** When implementation reaches the frontend/UI phase, the agent must **stop and explicitly tell the user** it's time to produce designs in Stitch, then build against the exported designs the user provides — never build a UI from scratch out of the agent's own aesthetic judgment. This rule is restated in `docs/05_DESIGN.md`, `docs/12_GUARDRAILS.md`, and `AGENTS.md` because it is the single most important "don't go off track" rule in this entire doc set, per the user's explicit instruction.

### 11.14 Deployment Topology Summary
```
Cloudflare Pages (frontend PWA)
        │
        ▼
Render free Web Service (FastAPI backend)  ──►  Neon Postgres (structured data)
        │
        ▼
Cloudflare R2 (images + generated PDF reports)
        │
Gmail SMTP / Brevo (officer notification email)
```
Every node in this topology has a genuinely free, non-expiring, no-custom-domain-required tier as of this research (September 2026) — this was independently verified, not assumed from any single source document.

---

## 12. Database & Rule-Pack Schema Overview

*(Full DDL, indices, and relationships live in `docs/06_SCHEMA.md` — this section is the conceptual overview only.)*

### 12.1 Core entity relationship overview
```
users (officers/supervisors/admins)
  └─< inspections (one officer, many inspections)
        ├─< inspection_images (one inspection, many images: front/back/sticker/listing)
        ├─< extracted_fields (one inspection, many typed fields; each links to a bounding box + source image)
        └─< violations (one inspection, many violations; each links to a rule_pack entry + extracted_field)
audit_logs (append-only; references inspections, extracted_fields, and the user who made each change)
rule_packs (versioned JSON; each has an effective_from/effective_to; inspections reference the rule_pack version used)
```

### 12.2 Rule-pack JSON shape (illustrative — full schema in `docs/06_SCHEMA.md`)
```json
{
  "rule_pack_version": "2026.02.01",
  "effective_from": "2026-02-01",
  "source_citation": "LM(PC) Second Amendment Rules, 2025 (G.S.R. 881(E))",
  "rules": [
    {
      "rule_id": "font-size-pdp",
      "applies_to": ["all"],
      "type": "font_height_by_pdp_area",
      "thresholds_mm": {
        "50": 1.0, "100": 1.5, "500": 2.0, "2500": 4.0, "gt_2500": 6.0
      }
    },
    {
      "rule_id": "pan-masala-rsp",
      "applies_to": ["pan_masala"],
      "type": "field_required",
      "field": "retail_sale_price",
      "note": "Small-pack exemption withdrawn as of 2026-02-01"
    }
  ]
}
```
This structure is what makes an amendment a **data change, not a code change** — the entire architectural point of §4.5/§9.2 step 7.

---

## 13. Implementation Roadmap Overview

*(Granular, checkable tasks live in `docs/07_IMPLEMENTATION_PLAN.md` and are mirrored 1:1 in `docs/08_TRACKER.md` — this is the phase-level summary only.)*

| Phase | Scope | Target |
|---|---|---|
| **Phase 0 — Spikes** | Validate the two riskiest unknowns before committing: (a) client-side vs. server-side OCR (§11.3), (b) barcode-calibration accuracy (§9.4) on real sample photos | Before Phase 1 feature work begins |
| **Phase 1 — MVP** | Core capture → OCR → extract → rule-check → evidence → report pipeline for physical packages; SQLite/local-first demo mode; basic auth | Hackathon-ready |
| **Phase 2 — Enhanced** | Full declaration set, font/legibility validation with calibration, multi-image support, human review queue, analytics dashboard, Neon/R2 production wiring | Post-hackathon, weeks 4–8 |
| **Phase 3 — E-commerce & Advanced** | E-commerce listing cross-checking, Bhashini integration, batch/warehouse mode | Weeks 8–12 |
| **Phase 4 — Production Readiness** | Government SSO, hardened offline sync, monitoring, deployment checklist (`docs/06_SCHEMA.md`/`docs/11_SECRETS_CHECKLIST.md` finalized), eMaap API adapter (aspirational) | Weeks 12–16+ |

---

## 14. Risk Analysis & Mitigation

### 14.1 Technical risks

| Risk | Mitigation |
|---|---|
| OCR accuracy on poor-quality field photos | PaddleOCR + Tesseract fallback, quality gate before OCR runs (§10.1), human review queue for low-confidence fields |
| Rule-engine complexity growing unmanageably | Start with the core declaration set, expand rule packs incrementally, keep rules as data not code |
| Performance on low-end officer devices | Client-side model size choice (tiny/small PP-OCRv6 tiers), optional server-side fallback |
| Offline storage limits on device | Compress images, cap local queue depth, smart incremental sync |
| Free-tier host cold starts affecting a live demo | Warm the Render instance before demos; design the client to tolerate a slow first request gracefully |

### 14.2 Regulatory risks

| Risk | Mitigation |
|---|---|
| Rule changes mid-development | Versioned rule packs (§12.2) — this is the core mitigation, not an afterthought |
| Citing an incorrect rule clause on a report | Verify every sub-clause citation against a primary source before shipping it in report text (§4.2 flags the specific unresolved ones) |
| Legal-liability exposure from an AI "ruling" | The mandatory "decision-support, not a legal ruling" disclaimer on every report (§10.9); the officer always makes the final call, never the software |
| eMaap-overlap claim being factually wrong in a pitch | Use the corrected framing from §3.4, not the earlier "eMaap has zero enforcement" claim |

### 14.3 Operational risks

| Risk | Mitigation |
|---|---|
| Officer resistance to a new tool | User-centric design, demonstrate concrete time savings early |
| Internet connectivity gaps in the field | Full offline-first capability is a Phase 1 requirement, not a stretch goal |
| Device compatibility across a range of officer phones | PWA approach avoids app-store fragmentation; test on representative low/mid-range Android devices |
| Data privacy of scanned commercial/consumer data | Local-first storage where possible, encryption in transit/at rest, a clear internal privacy policy before any pilot |

---

## 15. Success Metrics

| Metric | Target |
|---|---|
| Inspection time reduction | ~85% (from 10–15 min to under 2 min per package) |
| Enforcement coverage increase | Order-of-magnitude improvement vs. current manual coverage |
| OCR accuracy (character-level) | >95% target, validated against a real labeled test set — not assumed from vendor benchmarks alone |
| False positive rate (incorrect non-compliance flags) | <5% |
| False negative rate (missed violations) | <2% — the more legally important of the two error types |
| Officer adoption in a pilot | >80% active usage |

Qualitative: officer satisfaction/usability feedback, reduction in consumer complaints about non-compliant packages over time, judicial/administrative acceptance of the generated evidence.

---

## 16. Future Enhancements — PAID options (explicitly for AFTER the initial build, not now)

The user explicitly asked for this section to exist and to be clearly separated from the required-free MVP stack above. **Do not use any of these while building the initial project** — only revisit once the core system works end-to-end on the free stack in §11.

| Area | Free-tier MVP choice | Paid upgrade path (later, for quality/scale) |
|---|---|---|
| Hosting reliability | Render free (sleeps on idle) | Render/Fly.io paid always-on tier, or a small VPS |
| Database | Neon free | Neon Pro / Supabase Pro for guaranteed performance & backups |
| OCR accuracy | PaddleOCR PP-OCRv6 (free) | Commercial OCR (Google Cloud Vision / Azure AI Document Intelligence) as an accuracy-boost fallback layer for the hardest images |
| Compute for heavier models | CPU-only free tiers | A GPU inference endpoint (e.g., an NVIDIA L4-class instance) once volume justifies it |
| Email | Gmail SMTP / Brevo free | SendGrid/Mailgun/Postmark at real volume, once a custom domain is already owned |
| Language/voice | Bhashini free developer tier | Bhashini production/commercial tier if the platform scales to charged usage |
| Identity | Self-rolled JWT | MeriPehchan/Jan Parichay government SSO |
| Government integration | None in MVP | Formal eMaap API partnership, UMANG, DigiLocker |

---

## 17. Glossary

| Term | Meaning |
|---|---|
| LMPC | Legal Metrology (Packaged Commodities) [Rules, 2011] |
| DoCA | Department of Consumer Affairs |
| eMaap | India's national Legal Metrology portal (licensing/registration/verification) |
| PDP | Principal Display Panel — the primary label surface a declaration's font-size rule scales against |
| MRP | Maximum Retail Price |
| RSP | Retail Sale Price |
| OCR | Optical Character Recognition |
| CV | Computer Vision |
| PWA | Progressive Web Application |
| Rule pack | A versioned, dated JSON snapshot of the rules the engine checks against |
| LMO | Legal Metrology Officer |
| SIH | Smart India Hackathon |
| ULCA | Unified Language Contribution & Analysis (Bhashini's underlying platform) |

---

## 18. Source Notes & Known Conflicts (read alongside `docs/10_OPEN_QUESTIONS.md`)

1. **eMaap enforcement scope** — earlier research said "no enforcement"; later, more careful research found eMaap does cover some enforcement (licensing/registration). Corrected framing used throughout this document: §3.4. **[Resolved for pitch purposes — do not use the "zero enforcement" claim.]**
2. **MRP sub-clause lettering** — sources disagree between Rule 6(1)(d) and Rule 6(1)(f) for the MRP declaration requirement. **[Unresolved — verify against the bare act before hard-coding into a rule pack or printing on a report. See OQ in `docs/10_OPEN_QUESTIONS.md`.]**
3. **Font-height threshold table exact figures** — the table in §4.3 is consistent across the source that provided the most detail, but was not independently cross-verified against a second primary source in this session. **[Verify before production use — flagged, not blocking for a hackathon demo.]**
4. **DGQA/BIS association** — one lower-quality source draft associated DGQA (a defence-quality body) with this domain; treated as a likely research error, excluded from this document's regulatory-bodies list (§4.7). **[Do not repeat in a pitch.]**
5. **OCR accuracy benchmark numbers** — PaddleOCR's own published 94.5% OmniDocBench figure is a general benchmark, not specific to Indian product-label photos in field conditions; real-world accuracy on this project's actual use case is unverified until tested on a real dataset (see Phase 0 spike, §13).
6. **Client-side vs. server-side OCR** — not resolved by research; deliberately left as a Phase 0 spike decision rather than asserted (§11.3).

---

## 19. Appendix: Repository & Documentation Map

```
/
├── MASTER_CONTENT.md          ← you are here (single source of truth)
├── AGENTS.md                  ← operating rules for any AI coding agent working in this repo
├── session-start.md           ← slash-command: run at the start of a new session
├── session-continue.md        ← slash-command: run when resuming mid-task / after context loss
└── docs/
    ├── 00_README.md            ← human-facing map of this docs/ folder
    ├── 01_PRD.md                ← formal product requirements (goals, user stories, acceptance criteria)
    ├── 02_ROADMAP.md            ← phase-level roadmap with milestones
    ├── 03_TECHSPEC.md           ← full technical spec (architecture, APIs, NFRs, deployment)
    ├── 04_APPFLOW.md            ← screen-by-screen / step-by-step user flows per persona
    ├── 05_DESIGN.md             ← design system + the Stitch MCP hand-off rule
    ├── 06_SCHEMA.md             ← full DB schema (DDL) + rule-pack JSON schema
    ├── 07_IMPLEMENTATION_PLAN.md← granular, sequenced, checkable build tasks
    ├── 08_TRACKER.md            ← live status of every task in 07 (1:1 task-ID parity, enforced)
    ├── 09_DECISIONS.md          ← architecture decision records (ADR log)
    ├── 10_OPEN_QUESTIONS.md     ← every unresolved ambiguity found, with resolution status
    ├── 11_SECRETS_CHECKLIST.md ← every required API key/secret, where to get it free, how to store it
    ├── 12_GUARDRAILS.md         ← the anti-drift rulebook — read this before writing any code
    ├── 13_RECOVERY.md           ← what to do if an agent gets lost or a session resets
    ├── 14_TRANSLATION_AUDIT.md ← periodic "did the code actually implement the spec" fidelity audit
    └── CHANGELOG.md             ← dated log of what's actually been built
```

This document will not need to change often — it describes what the project *is*. Documents inside `docs/` change constantly as work progresses; this one is the anchor they all point back to.