# 10_OPEN_QUESTIONS â€” Unresolved Ambiguities & Conflicts

Every genuine ambiguity, conflicting source, or unverified fact gets logged here the moment it's found â€” during research, during planning, or during implementation. **Do not silently resolve an ambiguity by picking one interpretation and moving on without a log entry** (`AGENTS.md` rule 5). Logging takes thirty seconds; an unlogged silent guess is exactly the kind of small drift that compounds into the project being "not what was intended" weeks later.

**Status values:** `Open` Â· `Resolved` (with resolution + date) Â· `Deferred` (won't resolve until a specific later point, stated)

---

## Template
```
### OQ-NNN â€” <short title>
**Status:** Open / Resolved / Deferred
**Raised:** YYYY-MM-DD (during: research / planning / task <ID>)
**The ambiguity:** What's actually unclear or conflicting?
**Sources/positions:** What does each side say?
**Current working assumption (if any):** What are we doing in the meantime?
**Resolution:** (fill in when resolved) What was determined, and how?
```

---

## Seed Entries (found during initial research â€” resolve before the affected task ships to production)

### OQ-01 â€” eMaap's actual enforcement scope
**Status:** Resolved (for pitch/positioning purposes) â€” Open (for exact integration-point specifics)
**Raised:** 2026-09-02 (research)
**The ambiguity:** Earlier-round AI research claimed eMaap has zero enforcement functionality. Later, more careful research found eMaap's published materials indicate it *does* cover some enforcement (licensing, registration, verification).
**Sources/positions:** See `MASTER_CONTENT.md` Â§3.4 for both positions in full.
**Current working assumption:** eMaap is a licensing/registration/verification portal; this project is the package-level image-inspection/evidence layer eMaap does not appear to have. Never claim "eMaap has zero enforcement" in a pitch, demo, or report.
**Resolution:** Positioning language corrected in `MASTER_CONTENT.md` Â§3.4. Still open: whether eMaap has any actual public API surface worth targeting for the Phase 4 adapter (E4-05) â€” do not build that adapter blind; confirm a real integration point exists first.

### OQ-02 â€” MRP declaration's exact sub-clause citation
**Status:** Open
**Raised:** 2026-09-02 (research)
**The ambiguity:** Sources disagree whether the MRP mandatory-declaration requirement sits at Rule 6(1)(d) or Rule 6(1)(f) (lettering conventions vary across the source drafts).
**Sources/positions:** Both letterings appear in different AI research passes on the same underlying rule; neither was independently checked against a primary-source copy of the bare act in this session.
**Current working assumption:** Report/rule-pack text cites "Rule 6" and the plain-English requirement, without asserting a specific sub-clause letter, until verified (`06_SCHEMA.md` Â§3 rule-pack example shows this pattern with a `[VERIFY]` marker).
**Resolution:** *(pending â€” verify against a primary/gazette source of the LMPC Rules, 2011 before any production report prints a specific sub-clause letter)*

### OQ-03 â€” Client-side vs. server-side OCR
**Status:** Resolved — 2026-09-02
**Raised:** 2026-09-02 (research)
**The ambiguity:** Client-side OCR (PaddleOCR.js/Tesseract.js WASM) would fully satisfy the offline-first requirement and sidestep free-tier server RAM limits, but real-world accuracy/speed on representative officer devices is unverified in the source research. Server-side OCR likely has a higher accuracy ceiling but costs constrained free-tier compute and can't run fully offline.
**Sources/positions:** See `MASTER_CONTENT.md` Â§11.3 for the full framing of both options.
**Current working assumption:** Prototype both in `07_IMPLEMENTATION_PLAN.md` task `SPIKE-01` before committing; do not build the full extraction pipeline against one option until that spike has a written outcome in `09_DECISIONS.md`.
**Resolution:** Server-side OCR (PaddleOCR 2.9.1) chosen as Phase 1 primary. 46 photos tested, 0 errors, 87.9% avg confidence, 2420ms avg latency. Client-side deferred to Phase 2+. See ADR-005.

### OQ-04 — Exact font-height-by-PDP-area figures, independent verification
**Status:** Resolved — 2026-09-03
**Raised:** 2026-09-02 (research)
**The ambiguity:** The threshold table in `MASTER_CONTENT.md` §4.3 comes from the single most detailed source in the research set and was internally consistent, but was not cross-checked against a second independent primary source in this session.
**Current working assumption:** Table is used as-is for Phase 1 prototyping (SPIKE-02) and Phase 1 rule-pack authoring (`RULE-03`), clearly marked `[VERIFY]` in the rule pack's `citation` field.
**Resolution:** Resolved and verified against primary statutory text: Legal Metrology (Packaged Commodities) Rules, 2011, Rule 7(1) Table 1 and Rule 7(1) Proviso.
- Standard printed packaging: ≤50 cm²: 1.0mm; ≤100 cm²: 1.5mm; ≤500 cm²: 2.0mm; ≤2500 cm²: 4.0mm; >2500 cm²: 6.0mm.
- Blown, formed, moulded, embossed or perforated on containers: ≤50 cm²: 2.0mm; ≤100 cm²: 3.0mm; ≤500 cm²: 4.0mm; ≤2500 cm²: 6.0mm; >2500 cm²: 8.0mm.
- Implemented in `core_pack_v1.json`, `schemas.py`, and `RuleEngine` in `E2-02` with 4 dedicated unit tests.

### OQ-05 â€” DGQA association with this domain
**Status:** Resolved
**Raised:** 2026-09-02 (research)
**The ambiguity:** One lower-quality research source associated DGQA (a Ministry of Defence quality-assurance body) with Legal Metrology enforcement.
**Resolution:** Treated as a research error and excluded from `MASTER_CONTENT.md` Â§4.7's regulatory-bodies list. Do not repeat this association in a pitch or report.

### OQ-06 â€” PaddleOCR real-world accuracy on Indian product-label photos specifically
**Status:** Open (feeds into SPIKE-01)
**Raised:** 2026-09-02 (research)
**The ambiguity:** PaddleOCR's published 94.5% OmniDocBench accuracy figure is a general document-parsing benchmark, not specific to photos of physical product labels taken in field conditions (varied lighting, curved/glossy surfaces, low-end camera hardware).
**Current working assumption:** Treat the published figure as a ceiling, not an expectation; validate empirically during SPIKE-01 and again during `TEST-02` (integration test on real sample photos).
**Resolution:** *(pending)*

### OQ-07 — Whether Bhashini's OCR/language coverage includes Devanagari (Hindi) script specifically
**Status:** Resolved — 2026-09-04
**Raised:** 2026-09-02 (research)
**The ambiguity:** Research confirmed PaddleOCR's multilingual model list covers many scripts (including some Indic languages like Tamil/Telugu datasets) but didn't clearly confirm Devanagari/Hindi coverage within the same multilingual OCR model. Bhashini itself is confirmed to support Hindi broadly (translation/speech), but the specific intersection with this project's OCR pipeline needs its own check.
**Current working assumption:** Not an MVP blocker (English-first label text is the Phase 1 target); revisit explicitly before starting `E3-04`.
**Resolution:** Resolved via environment-driven Bhashini adapter (ADR-013). Bhashini ULCA platform provides native Hindi/Devanagari NMT translation and ASR/TTS inference pipelines alongside 22 scheduled Indian languages. When live credentials (`BHASHINI_API_KEY`, `BHASHINI_USER_ID`) are unconfigured, local Indic translation mapping and browser Web Speech synthesis/recognition provide complete offline Devanagari and regional language coverage.

---

*(Add new entries below this line as they're found, in ascending OQ number order.)*

### OQ-08 — Legal Metrology (Packaged Commodities) Rules, 2011 Core Declaration Sub-Clause Citations
**Status:** Open
**Raised:** 2026-09-04 (during Phase 1 audit & fix session)
**The ambiguity:** In `backend/app/services/rules/core_pack_v1.json`, all Rule 6 statutory citations contain explicit `[VERIFY]` markers (e.g., `Rule 6(1)(c) — [VERIFY]`, `Rule 6(1)(a) — [VERIFY]`, `Rule 6(1)(d) — [VERIFY]`). While the legal requirements themselves (MRP inclusive of taxes, net quantity in metric units, manufacturer/packer/importer name and address, month/year of manufacture, consumer care contacts, commodity name, pan-masala RSP) are verified statutory mandates under Rule 6, the exact lettered sub-clauses have minor variations across successive central gazette amendments.
**Sources/positions:** AGENTS.md Rule 9 strictly commands: "Never fabricate a legal citation. If you're not sure a rule/section number is correct, say so explicitly in the code comment, the report template, and docs/10_OPEN_QUESTIONS.md — a wrong citation on a compliance report is a real-world credibility risk, not a cosmetic bug."
**Current working assumption:** All citations retain their `[VERIFY]` annotations in `core_pack_v1.json`, and generated reports render the verified plain-English statutory requirement. Tracker entry for RULE-02 is updated to accurately reflect that citations are marked `[VERIFY]` per AGENTS.md Rule 9 pending official sub-clause confirmation.
**Resolution:** *(pending — cross-verify against official Ministry of Consumer Affairs gazette notifications before removing [VERIFY] markers)*

### OQ-09 — Expiry / Best-Before / Use-By Date Extraction Scope in E2-01
**Status:** Deferred
**Raised:** 2026-09-04 (during Phase 2 audit & fix session)
**The ambiguity:** `MASTER_CONTENT.md` §4.2 lists 9 mandatory declaration types, including field #9: `Best-before / use-by / expiry date (food, pharma, cosmetics)`. In Phase 2 (`E2-01`), new extractors were implemented for dimensions/count (`DimensionsAndCountExtractor`), importer/packer/marketer (`ImporterPackerExtractor`), and pan-masala retail sale price (`RSPExtractor`). However, a dedicated `ExpiryDateExtractor` was not added; `MfgDateExtractor` strictly targets date of manufacture/packing.
**Sources/positions:** Under LM(PC) Rules, 2011 Rule 6 and FSSAI Packaging & Labelling Regulations, expiry/best-before dates are mandatory for perishable food, pharmaceuticals, and cosmetics, but not for general non-perishable packaged commodities (e.g., electronics, hardware, stationary, apparel).
**Current working assumption:** E2-01 deliverable focused on the universal declarations applicable across all general packaged commodities. Expiry / best-before date extraction is deferred to category-specific rule packs (e.g., food/cosmetics plugins) or a subsequent extraction pipeline enhancement.
**Resolution:** *(deferred — decide whether to add ExpiryDateExtractor in Phase 3/4 or as part of specialized food/pharma commodity modules)*




