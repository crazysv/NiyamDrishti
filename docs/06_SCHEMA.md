# 06_SCHEMA — Database Schema & Rule-Pack Schema

Target: PostgreSQL (Neon, production) with SQLite as a structurally-compatible local/offline/dev fallback (`03_TECHSPEC.md`). Written to be SQLAlchemy-model-friendly — treat this as the contract the ORM models must match, not just documentation written after the fact.

---

## 1. Entity Relationship Overview

```
users ──< inspections ──< inspection_images
              │
              ├──< extracted_fields ──> (source) inspection_images
              │         │
              │         └──< violations ──> rule_packs.rules[rule_id]
              │
              └──< reports

audit_logs  ──> inspections, extracted_fields, users (append-only, references only)
rule_packs  (versioned, independent lifecycle — referenced by inspections.rule_pack_version)
```

---

## 2. Tables

### `users`
```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('officer', 'supervisor', 'admin')),
    region          TEXT,                          -- jurisdiction, used for dashboard filtering
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `inspections`
```sql
CREATE TABLE inspections (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    officer_id          UUID NOT NULL REFERENCES users(id),
    status              TEXT NOT NULL CHECK (status IN
                            ('draft', 'processing', 'needs_review', 'completed', 'sync_pending')),
    commodity_category  TEXT,                       -- e.g. 'general', 'pan_masala', 'medical_device'
    rule_pack_version   TEXT NOT NULL,               -- FK-like reference to rule_packs.version; frozen at creation, immutable
    is_self_check       BOOLEAN NOT NULL DEFAULT FALSE, -- Phase 3+: manufacturer self-check, structurally distinct, never joined into enforcement dashboards
    region              TEXT,
    captured_offline    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    synced_at           TIMESTAMPTZ                  -- null until an offline-captured inspection reaches the server
);
CREATE INDEX idx_inspections_officer ON inspections(officer_id);
CREATE INDEX idx_inspections_status ON inspections(status);
CREATE INDEX idx_inspections_created ON inspections(created_at);
```
**Invariant:** `rule_pack_version` is set once at creation and never changed afterward, even if a newer rule pack is later activated — this is what guarantees a past inspection's recorded verdict never silently changes (`01_PRD.md` US-04, `04_APPFLOW.md` §4).

### `inspection_images`
```sql
CREATE TABLE inspection_images (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id   UUID NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    image_role      TEXT NOT NULL CHECK (image_role IN
                        ('front_pdp', 'back_panel', 'side_panel', 'sticker', 'ecommerce_listing')),
    storage_url     TEXT NOT NULL,                   -- Cloudflare R2 object URL (signed, time-limited when served)
    width_px        INTEGER,
    height_px       INTEGER,
    calibration_scale_mm_per_px  NUMERIC,            -- null if uncalibrated (no barcode reference found)
    quality_check_passed BOOLEAN NOT NULL DEFAULT FALSE,
    captured_at     TIMESTAMPTZ NOT NULL,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_images_inspection ON inspection_images(inspection_id);
```

### `extracted_fields`
```sql
CREATE TABLE extracted_fields (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id       UUID NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    source_image_id     UUID NOT NULL REFERENCES inspection_images(id),
    field_type          TEXT NOT NULL,                -- 'mrp', 'net_quantity', 'manufacturer_address',
                                                        -- 'mfg_date', 'consumer_care', 'country_of_origin',
                                                        -- 'retail_sale_price', 'font_height', etc.
    raw_text            TEXT,
    parsed_value         TEXT,                         -- normalized value, type depends on field_type
    confidence          NUMERIC NOT NULL,              -- 0.0–1.0
    bounding_box         JSONB NOT NULL,                -- {"x":, "y":, "w":, "h":}
    verdict              TEXT NOT NULL CHECK (verdict IN
                            ('pass', 'fail', 'needs_review', 'not_applicable')),
    reviewed_by_officer  BOOLEAN NOT NULL DEFAULT FALSE,
    officer_override_value TEXT,                       -- null unless the officer corrected it
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_fields_inspection ON extracted_fields(inspection_id);
CREATE INDEX idx_fields_verdict ON extracted_fields(verdict);
```

### `violations`
```sql
CREATE TABLE violations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id       UUID NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    extracted_field_id  UUID REFERENCES extracted_fields(id),   -- null for a "missing declaration entirely" violation
    rule_id             TEXT NOT NULL,                -- matches a rule_id inside the active rule_pack's JSON
    rule_pack_version   TEXT NOT NULL,                -- redundant with inspections.rule_pack_version but kept for query convenience
    description         TEXT NOT NULL,                -- human-readable finding text
    citation             TEXT,                         -- rule/section reference — ONLY populated if verified (see 10_OPEN_QUESTIONS.md)
    severity             TEXT NOT NULL CHECK (severity IN ('minor', 'major', 'critical')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_violations_inspection ON violations(inspection_id);
CREATE INDEX idx_violations_rule ON violations(rule_id);
```

### `reports`
```sql
CREATE TABLE reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id   UUID NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    format          TEXT NOT NULL CHECK (format IN ('pdf', 'editable')),
    storage_url     TEXT NOT NULL,                   -- Cloudflare R2
    generated_by    UUID NOT NULL REFERENCES users(id),
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reports_inspection ON reports(inspection_id);
```

### `rule_packs`
```sql
CREATE TABLE rule_packs (
    version          TEXT PRIMARY KEY,                -- e.g. '2026.02.01'
    effective_from   DATE NOT NULL,
    effective_to     DATE,                             -- null = still current/open-ended
    source_citation  TEXT,                              -- e.g. 'LM(PC) Second Amendment Rules, 2025 (G.S.R. 881(E))'
    rules_json       JSONB NOT NULL,                    -- see §3 below for shape
    is_active        BOOLEAN NOT NULL DEFAULT FALSE,     -- exactly one row should be true at a time — enforce in application logic
    created_by        UUID NOT NULL REFERENCES users(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `audit_logs` (append-only — no UPDATE or DELETE code path should ever touch this table)
```sql
CREATE TABLE audit_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id       UUID NOT NULL REFERENCES users(id),
    action              TEXT NOT NULL,                 -- 'field_override', 'rule_pack_activated', 'user_created', etc.
    entity_type         TEXT NOT NULL,                 -- 'extracted_field', 'rule_pack', 'user', ...
    entity_id           TEXT NOT NULL,
    before_value         JSONB,
    after_value          JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_actor ON audit_logs(actor_user_id);
```

---

## 3. Rule-Pack JSON Schema

Stored in `rule_packs.rules_json`. This is what makes a regulatory amendment a **data change**, not a code change (`MASTER_CONTENT.md` §4.5/§12.2).

```json
{
  "rule_pack_version": "2026.02.01",
  "effective_from": "2026-02-01",
  "effective_to": null,
  "source_citation": "LM(PC) Second Amendment Rules, 2025 (G.S.R. 881(E))",
  "rules": [
    {
      "rule_id": "declaration-present-mrp",
      "applies_to": ["all"],
      "type": "field_required",
      "field": "mrp",
      "citation": "Rule 6 — [VERIFY exact sub-clause before shipping to production, see 10_OPEN_QUESTIONS.md]",
      "severity": "critical"
    },
    {
      "rule_id": "font-size-pdp",
      "applies_to": ["all"],
      "type": "font_height_by_pdp_area",
      "thresholds_mm": { "50": 1.0, "100": 1.5, "500": 2.0, "2500": 4.0, "gt_2500": 6.0 },
      "citation": "Rule 7 [VERIFY]",
      "severity": "major",
      "requires_calibration": true
    },
    {
      "rule_id": "pan-masala-rsp",
      "applies_to": ["pan_masala"],
      "type": "field_required",
      "field": "retail_sale_price",
      "note": "Small-pack exemption withdrawn as of 2026-02-01",
      "citation": "LM(PC) Second Amendment Rules, 2025",
      "severity": "critical"
    }
  ]
}
```

**Rule schema field notes:**
- `type` is an enum the rule engine dispatches on (`field_required`, `font_height_by_pdp_area`, `format_match`, `date_validity`, etc.) — add new types deliberately, document them here when added.
- `applies_to` scopes a rule to specific `commodity_category` values on the inspection, or `"all"`.
- `citation` should carry a `[VERIFY]` marker (as shown above) for anything not yet confirmed against a primary source — never silently drop the marker just to make output look cleaner; see `12_GUARDRAILS.md` "Never fabricate a legal citation."
- `requires_calibration: true` tells the engine (and the report renderer) to visibly flag the result as an estimate if `inspection_images.calibration_scale_mm_per_px` is null for the relevant image.

---

## 4. Migration & Local/Offline Compatibility Notes

- SQLAlchemy models are the single source of truth for actual column definitions; this file must be kept in sync whenever a model changes (`12_GUARDRAILS.md`).
- Alembic migrations are additive-first: prefer nullable-then-backfill over destructive column changes, given inspections are meant to be permanently retained (`01_PRD.md` NFR "Data retention").
- SQLite (local/offline/dev) does not support `UUID`, `JSONB`, or `TIMESTAMPTZ` natively — use SQLAlchemy's cross-dialect types (`String` for UUIDs stored as text, `JSON` for JSONB, `DateTime` with explicit UTC handling) so the same models work against both engines without a parallel schema.
- `bounding_box` and `rules_json` must round-trip identically between SQLite and Postgres — write a test for this explicitly given how central evidence-mapping is to the product (`07_IMPLEMENTATION_PLAN.md` should include this as an early task, not an afterthought).
