# 03_TECHSPEC â€” Technical Specification

This is the authoritative technical reference. Product context lives in `01_PRD.md`; this file is *how*, not *why*. Tech-stack rationale and free-tier verification detail lives in `../MASTER_CONTENT.md` Â§11 â€” this file gives the buildable specifics: versions, config, API surface, and deployment.

---

## 1. Architecture (recap + detail)

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  CLIENT â€” Next.js PWA (installable, offline-capable)           â”‚
â”‚  - Capture UI (react-webcam)                                   â”‚
â”‚  - Quality-gate checks (client-side, before upload)            â”‚
â”‚  - Offline queue (Dexie.js / IndexedDB)                        â”‚
â”‚  - (per Phase 0 spike outcome) optional client-side OCR         â”‚
â”‚  - Evidence viewer (react-zoom-pan-pinch)                      â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                     â”‚ HTTPS / REST (JSON), resumable sync
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  API â€” FastAPI (Python 3.11+)                                   â”‚
â”‚  - /auth        - /inspections     - /rule-packs                â”‚
â”‚  - /images       - /reports         - /analytics                â”‚
â”‚  Services: OCR orchestration Â· rule engine Â· evidence mapping   â”‚
â”‚  Â· report generation (WeasyPrint) Â· review-queue logic          â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                â”‚                                   â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Neon PostgreSQL               â”‚   â”‚  Cloudflare R2                â”‚
â”‚  (SQLAlchemy + Alembic)        â”‚   â”‚  (images, generated PDFs)     â”‚
â”‚  Local dev/offline: SQLite     â”‚   â”‚  Local dev/offline: filesystemâ”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## 2. Approved Tech Stack (buildable reference table)

> Full rationale + free-tier verification is in `../MASTER_CONTENT.md` Â§11. This table is the quick lookup during implementation. **Do not substitute a row without logging why in `09_DECISIONS.md`.**

| Layer | Choice | Version (as of Sept 2026) |
|---|---|---|
| Frontend framework | Next.js | 14+ (App Router) |
| Frontend language | TypeScript | latest stable |
| Styling | Tailwind CSS | latest stable |
| Frontend hosting | Cloudflare Pages (primary) / Vercel Hobby (alt) | â€” |
| Backend framework | FastAPI | latest stable |
| Backend language | Python | 3.11+ |
| Backend hosting | Render free Web Service (primary) | â€” |
| Database | Neon (PostgreSQL) | PG 15+ |
| Local/offline DB | SQLite | bundled |
| ORM | SQLAlchemy | 2.x, async |
| Migrations | Alembic | latest |
| Object storage | Cloudflare R2 | â€” |
| OCR (primary) | PaddleOCR PP-OCRv6 (tiny/small tier) | released June 2026 |
| OCR (fallback) | Tesseract | 5.x |
| CV/preprocessing | OpenCV (opencv-python) + Pillow | latest stable |
| Barcode calibration | zxing-cpp | latest stable (ADR-006 amendment) |
| PDF generation | WeasyPrint (primary) / FPDF2 (fallback) | latest stable |
| Auth | Self-rolled JWT (python-jose + passlib/bcrypt) | â€” |
| Email | Gmail SMTP (primary) / Brevo (alt) | â€” |
| Containerization | Docker + Docker Compose | latest stable |
| CI/CD | GitHub Actions | â€” |
| Lint/format/type-check | Ruff, Black, mypy | latest stable |
| Testing | pytest, pytest-cov, httpx | latest stable |

## 3. API Surface (Phase 1 MVP scope â€” extend, don't replace, in later phases)

All endpoints prefixed `/api/v1`. Auth via `Authorization: Bearer <JWT>` unless noted.

| Method & Path | Purpose |
|---|---|
| `POST /auth/login` | Officer/admin login â†’ JWT |
| `POST /auth/refresh` | Refresh token |
| `POST /inspections` | Create a new inspection (returns `inspection_id`) |
| `POST /inspections/{id}/images` | Upload one image to an inspection (front/back/side/sticker) |
| `POST /inspections/{id}/process` | Trigger OCR + extraction + rule evaluation for the inspection |
| `GET /inspections/{id}` | Full inspection detail: images, extracted fields, verdicts, evidence boxes |
| `PATCH /inspections/{id}/fields/{field_id}` | Officer review: confirm/correct an extracted field (writes to audit log) |
| `POST /inspections/{id}/report` | Generate PDF report (returns a Cloudflare R2 URL) |
| `GET /inspections` | Search/filter: by officer, date range, region, violation type, product |
| `GET /rule-packs` | List rule-pack versions |
| `GET /rule-packs/{version}` | Fetch a specific rule pack (full JSON) |
| `POST /rule-packs` *(admin only)* | Upload a new rule-pack version |
| `POST /rule-packs/{version}/activate` *(admin only)* | Set the active rule pack |
| `GET /analytics/summary` | Dashboard aggregate data (supervisor/admin) |

Every endpoint that returns or accepts an extracted field must include `bounding_box` and `confidence` â€” never strip these for "simplicity"; they are the evidence-mapping feature, not optional metadata.

## 4. Data Flow (per inspection â€” expanded from Master Content Â§9.2)

1. Client creates inspection â†’ `POST /inspections`.
2. Client uploads image(s) â†’ `POST /inspections/{id}/images` (queued locally first if offline; flushed on reconnect).
3. Client (or server, per the Phase 0 spike decision) runs quality gate; rejected images prompt a retake with a specific reason.
4. `POST /inspections/{id}/process` triggers: preprocessing â†’ OCR â†’ declaration extraction â†’ optical calibration â†’ rule engine evaluation â†’ evidence mapping.
5. Response includes every extracted field with its verdict, confidence, and bounding box.
6. Fields below the confidence threshold (baseline 85% â€” tune empirically in Phase 1 testing, log the tuned value in `09_DECISIONS.md`) surface in the review queue.
7. Officer reviews/corrects â†’ `PATCH /inspections/{id}/fields/{field_id}` â†’ audit log entry written.
8. `POST /inspections/{id}/report` renders the PDF (WeasyPrint) and stores it in R2.

## 5. Non-Functional Requirements (implementation detail)

| NFR | Implementation note |
|---|---|
| Offline capability | Client queue (Dexie.js) stores pending captures + metadata; sync is per-item and resumable, never "all or nothing." Server must accept out-of-order/backfilled timestamps gracefully. |
| Free-tier resource limits | Backend must run within Render free-tier RAM; this is the direct reason OCR model-size choice (`MASTER_CONTENT.md` Â§11.3) matters â€” do not casually upgrade to a heavier OCR model without checking it still fits. |
| Cold starts | Render free tier sleeps on inactivity. Client should show a clear "connecting..." state rather than appearing frozen on the first request after idle. |
| Security | JWT expiry + refresh; bcrypt password hashing; rate limiting via slowapi on auth endpoints; all image/report URLs from R2 should be time-limited signed URLs, not permanently public. |
| Auditability | `audit_logs` table is append-only at the application layer â€” no update/delete code path should ever touch it. |
| Report legal safety | The disclaimer text (`MASTER_CONTENT.md` Â§10.9) lives in one shared template partial, never duplicated/hand-typed per report type, so it can't be accidentally omitted in a new report variant. |

## 6. Environment Configuration

See `11_SECRETS_CHECKLIST.md` for the full list of required environment variables and where to obtain each one for free. High-level groups:
- Database connection (Neon connection string / local SQLite path for dev)
- Cloudflare R2 credentials (access key, secret, bucket, endpoint)
- JWT signing secret
- SMTP credentials (Gmail App Password or Brevo API key)
- OCR model paths/cache directory
- Active rule-pack version pointer (or "latest" resolution logic)

`.env.example` must be kept in sync with this list at all times â€” see `12_GUARDRAILS.md` for the enforced rule on secrets hygiene.

## 7. Deployment

- **Local dev:** Docker Compose spins up API + local Postgres (or SQLite mode) + a local file-storage stand-in for R2.
- **Staging/demo:** Cloudflare Pages (frontend) + Render (backend) + Neon (DB) + Cloudflare R2 (storage) â€” the exact topology in `MASTER_CONTENT.md` Â§11.14.
- **CI:** GitHub Actions runs lint (Ruff), type-check (mypy), and tests (pytest) on every push; deploy step only on `main`.

## 8. Mobile (Phase 3+, conditional)

The PWA is the default and required delivery target through Phase 2. Only evaluate wrapping it with **Capacitor** (Phase 3+) if a genuine requirement emerges that the PWA cannot meet (e.g., an app-store presence is mandated for pilot deployment). Do not build a separate native codebase â€” Capacitor wraps the existing PWA rather than duplicating it.

## 9. What's explicitly deferred (do not build early)

See `MASTER_CONTENT.md` Â§5 and Â§16 â€” any government API integration, Bhashini, paid-tier upgrades, and native mobile are all out of Phase 1/2 scope. If you're implementing something from this list, check `02_ROADMAP.md` first; you're probably ahead of schedule.

