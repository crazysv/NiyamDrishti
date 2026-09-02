# 11_SECRETS_CHECKLIST — Required Credentials & Environment Variables

**Rule zero: never commit a real secret to the repository.** `.env` is git-ignored; `.env.example` (kept in this repo, tracked) lists every variable name with a placeholder value and a comment, never a real value. Every entry below must appear in `.env.example` (`SETUP-03` in `07_IMPLEMENTATION_PLAN.md`). If you add a new secret mid-build, add it here and to `.env.example` in the same turn.

---

## How to use this checklist

- ✅ **Required for MVP** — needed for Phase 1 to run end-to-end.
- 🔜 **Future phase** — not needed yet; don't provision it early just because it's on this list.
- Every row states exactly where to get it **for free**, matching the verified stack in `MASTER_CONTENT.md` §11.

| Variable | Required? | What it's for | Where to get it (free) | Notes |
|---|---|---|---|---|
| `DATABASE_URL` | ✅ MVP | Postgres connection string (Neon) | Create a free project at neon.tech — no card required | Local dev can point this at a local SQLite/Postgres instead; see `03_TECHSPEC.md` §6 |
| `JWT_SECRET_KEY` | ✅ MVP | Signs/verifies auth tokens | Generate locally (e.g. `openssl rand -hex 32`) — never fetched from a third party | Rotate before any real pilot deployment |
| `JWT_ALGORITHM` | ✅ MVP | Token signing algorithm (e.g. `HS256`) | Set directly, not a secret | |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ MVP | Token lifetime | Set directly | |
| `R2_ACCOUNT_ID` | ✅ MVP | Cloudflare R2 account identifier | Cloudflare dashboard → R2 | Free tier: 10GB storage, zero egress (`MASTER_CONTENT.md` §11.4) |
| `R2_ACCESS_KEY_ID` | ✅ MVP | R2 API credential | Cloudflare dashboard → R2 → Manage API Tokens | |
| `R2_SECRET_ACCESS_KEY` | ✅ MVP | R2 API credential | Cloudflare dashboard → R2 → Manage API Tokens | |
| `R2_BUCKET_NAME` | ✅ MVP | Target bucket for images/reports | Create in Cloudflare dashboard | |
| `R2_ENDPOINT_URL` | ✅ MVP | S3-compatible endpoint for the account | Cloudflare dashboard → R2 | |
| `SMTP_HOST` / `SMTP_PORT` | ✅ MVP | Email delivery (Gmail SMTP default) | `smtp.gmail.com`, port 587 | See ADR-003 in `09_DECISIONS.md` for why Gmail SMTP over Resend |
| `SMTP_USERNAME` | ✅ MVP | Sending account | Any Gmail account used for the project | |
| `SMTP_APP_PASSWORD` | ✅ MVP | Gmail App Password (not the account password) | Google Account → Security → App Passwords (requires 2FA enabled on the account) | Never use the real account password here |
| `OCR_MODEL_CACHE_DIR` | ✅ MVP | Local path PaddleOCR/Tesseract cache to | Set directly, not a secret | On constrained hosts (e.g. Hugging Face Spaces), must point to a writable path like `/tmp` — see `MASTER_CONTENT.md` §11.2/§11.3 caveats |
| `ACTIVE_RULE_PACK_VERSION` | ✅ MVP | Which rule pack the engine uses by default | Set after `RULE-02` seeds the initial rule pack | Not a secret, but must be explicit, never silently "latest" without an admin action (`06_SCHEMA.md` `rule_packs.is_active`) |
| `CORS_ALLOWED_ORIGINS` | ✅ MVP | Which frontend origin(s) may call the API | Set directly (Cloudflare Pages URL, local dev URL) | |
| `BREVO_API_KEY` | 🔜 Future (email scale-up) | Alternative email provider if Gmail SMTP limits are hit | brevo.com free-tier signup | Only provision if/when actually needed |
| `BHASHINI_API_KEY` / `BHASHINI_USER_ID` | 🔜 Phase 3 (`E3-04`) | Bhashini ULCA API access | Sign up at bhashini.gov.in (ULCA portal) | Confirm current sign-up/approval process at the time (`OQ-07`, `E3-03`) — do not block Phase 1/2 on this |
| Government SSO credentials (MeriPehchan/Jan Parichay) | 🔜 Phase 4 (`E4-01`) | Officer identity via government SSO | Requires a formal integration process | Not provisioned until Phase 4 planning begins |
| eMaap API credentials | 🔜 Phase 4 (`E4-05`) | Aspirational adapter | Unconfirmed whether a public integration point exists (`OQ-01`) | Do not provision speculatively |

---

## Storage & hygiene rules

1. `.env` is listed in `.gitignore` from `SETUP-01` onward — verify this before the first commit that touches any real credential.
2. `.env.example` must always have a placeholder for every variable above, with a one-line comment on where to get it — keep it in sync with this file.
3. Never paste a real secret into a chat log, a commit message, an issue, or a Stitch design prompt.
4. Rotate `JWT_SECRET_KEY` and any provider API keys before any real pilot/production deployment (`04_TRACKER` `DEPLOY-04`/`E4-06`).
5. If a secret is ever accidentally committed, treat it as compromised — rotate it immediately, don't just remove it from a future commit (git history retains it).
