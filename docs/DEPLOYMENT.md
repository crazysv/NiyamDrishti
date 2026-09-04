# DEPLOYMENT.md — Production & Staging Deployment Guide (MVP)

This guide documents the exact steps to deploy the full **NiyamDrishti** stack to the 100%-free production topology defined in `MASTER_CONTENT.md` §11.14 and `docs/03_TECHSPEC.md` §7.

---

## 1. Architecture Topology

```
                  +-------------------------------+
                  |       Cloudflare Pages        |
                  |     (Next.js PWA Client)      |
                  |  https://niyamdrishti.pages.dev|
                  +---------------+---------------+
                                  |
                                  | HTTPS / REST
                                  v
                  +-------------------------------+
                  |        Render Web Service     |
                  |   (FastAPI Docker Container)  |
                  | https://niyamdrishti-api.onrender.com
                  +-------+---------------+-------+
                          |               |
             Async SQL    |               | Presigned URLs
             (asyncpg)    v               v
+-----------------------------+       +-----------------------------+
|        Neon Postgres        |       |        Cloudflare R2        |
|    (Serverless Database)    |       |   (Zero-Egress Object Store)|
+-----------------------------+       +-----------------------------+
```

---

## 2. Component Deployment Steps

### 2.1 Backend: Render Free Web Service (`DEPLOY-01`)
The backend is packaged as a lightweight Docker container with OpenCV, WeasyPrint/FPDF2, and Tesseract OCR dependencies.

1. **Deploy via Blueprint (`render.yaml`):**
   - Log into [Render](https://render.com).
   - Go to **Blueprints** -> **New Blueprint Instance**.
   - Connect the `NiyamDrishti` GitHub repository.
   - Render will detect `render.yaml` and configure the `niyamdrishti-api` web service automatically.
2. **Configure Environment Secrets in Render Dashboard:**
   - `DATABASE_URL`: Your Neon Postgres async connection string (`postgresql+asyncpg://user:pass@ep-xyz.neon.tech/neondb?sslmode=require`).
   - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL`: Cloudflare R2 credentials.
   - `CORS_ALLOWED_ORIGINS`: `https://niyamdrishti.pages.dev,http://localhost:3000`.
3. **Health Check:**
   - Render monitors `GET /health`.
   - Returns `{"status": "healthy", "database": "connected"}`.

### 2.2 Backend Alternative / High-Memory Host: Hugging Face Spaces (16 GB Free RAM)
To permanently eliminate the 512 MB memory limit of Render free tier and handle multi-officer concurrent inspections with zero OOM crash risk, deploy the backend to Hugging Face Spaces:

1. **Create Space on Hugging Face:**
   - Log in to [Hugging Face](https://huggingface.co).
   - Click **Spaces** -> **New Space**.
   - Name: `niyamdrishti-backend`
   - License: `mit` / `apache-2.0`
   - Space SDK: **Docker** (Blank)
   - Hardware: **CPU Basic · 2 vCPU · 16 GB RAM (Free)** (No credit card needed).
2. **Push Backend Code:**
   - Clone the new Space repo locally or push from your git terminal:
     ```bash
     git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/niyamdrishti-backend
     git subtree push --prefix backend hf main
     ```
3. **Configure Secrets:**
   - In Space **Settings** -> **Variables and secrets**, add:
     - `DATABASE_URL`: Your Neon connection string
     - `JWT_SECRET_KEY`: Secret string
     - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`: Cloudflare R2 secrets
     - `APP_ENV`: `production`
     - `CORS_ALLOWED_ORIGINS`: `https://niyamdrishti.vercel.app,https://niyamdrishti.pages.dev,http://localhost:3000`
4. **Endpoint:**
   - Public API URL: `https://YOUR_USERNAME-niyamdrishti-backend.hf.space`
   - Update `NEXT_PUBLIC_API_BASE_URL` in frontend Vercel/Cloudflare Pages to point to this URL.

### 2.3 Frontend: Cloudflare Pages & Vercel (`DEPLOY-02`)
The frontend is a responsive Next.js Progressive Web App with offline-first IndexedDB storage.

1. **Deploy via Cloudflare Dashboard:**
   - Go to [Cloudflare Dashboard](https://dash.cloudflare.com) -> **Workers & Pages** -> **Create application** -> **Pages**.
   - Connect GitHub repository `NiyamDrishti`.
   - **Build settings:**
     - Framework preset: `Next.js`
     - Root directory: `frontend`
     - Build command: `npm run build`
     - Output directory: `.next` (or static export `out`)
   - **Environment variables:**
     - `NEXT_PUBLIC_API_BASE_URL`: `https://niyamdrishti-api.onrender.com`
2. **Deploy via CLI:**
   ```bash
   cd frontend
   npx wrangler pages deploy .next --project-name niyamdrishti
   ```

### 2.3 Cold-Start Mitigation & UX (`DEPLOY-03`)
- Render free-tier containers spin down to 0 after 15 minutes of inactivity.
- On cold boot, waking up takes ~30–45 seconds.
- **Client-Side Safeguard (`ColdStartBanner.tsx`):**
  - The client automatically pings `/health` upon opening.
  - If the server does not respond within 1.8 seconds, a non-intrusive banner appears:
    `"Waking Server from Sleep (Xs) — Render free-tier container boots in ~30s after inactivity. Offline camera & local inspection queuing remain 100% active."`
  - Once healthy, a green `"Backend Connected"` confirmation appears for 3.5s and smoothly dismisses.
  - Field officers are never blocked — all photos, barcodes, and provisional extractions are saved locally in Dexie IndexedDB.

### 2.4 Secrets Checklist Walkthrough (`DEPLOY-04`)
Before launching the service:
- [x] `.env` is listed in `.gitignore` (verified).
- [x] `.env.example` in `backend/.env.example` has exact placeholders matching `docs/11_SECRETS_CHECKLIST.md`.
- [x] No plaintext passwords or tokens committed to source control.
- [x] `JWT_SECRET_KEY` generated cryptographically (`openssl rand -hex 32`).
- [x] Neon database URL uses `postgresql+asyncpg://` schema with SSL enabled.
- [x] Cloudflare R2 bucket configured with 100% private access (all client downloads use signed URLs expiring in 900s).

---

## 3. Production Pilot Rollout Operations & Audit Checklist (`E4-06`)

This checklist must be executed and confirmed prior to deploying NiyamDrishti into a live regulatory field trial or district pilot.

### 3.1 Automated Pre-Flight System Audit
Execute the automated pre-flight audit tool from the backend container/environment:
```bash
python scripts/pilot_readiness_check.py
```
**Verification Gates:**
- [x] Database connectivity & 8 statutory tables mapped in ORM (`users`, `inspections`, `inspection_images`, `extracted_fields`, `violations`, `rule_packs`, `audit_logs`, `reports`).
- [x] Statutory Legal Metrology rule pack loaded (`core_pack_v1.json`, 12 active rules matching LMPC Rules 2011).
- [x] Evidentiary immutability engine active (FIPS PUB 180-4 SHA-256 and SQLAlchemy `PermissionError` on UPDATE/DELETE).
- [x] Object storage configured (Cloudflare R2 for production, local filesystem fallback for development).
- [x] Dual-mode government integration adapters operational (MeriPehchan SSO, eMaap National Portal, Bhashini ULCA).
- [x] Observability text exposition verified (`GET /metrics`).

### 3.2 Field Officer Device & PWA Readiness
- [ ] **Device Specs:** Mid-range Android smartphone (Android 11+, Chrome 110+, camera autofocus).
- [ ] **PWA Installation:** Open `https://niyamdrishti.pages.dev` in Chrome, tap `"Add to Home Screen"`, and confirm standalone window launch.
- [ ] **Offline Storage:** Verify device has at least 50MB free storage. Confirm `useStorageQuota` displays green status (capacity for 50 offline inspection packages).
- [ ] **Quality Gates:** Verify blur, glare, and barcode scale calibration gates correctly warn on low-quality captures with specific retake guidance.

### 3.3 Evidentiary & Courtroom Defensibility
- [ ] **Digital Chain of Custody:** Verify every captured label photo receives a SHA-256 fingerprint on intake.
- [ ] **Tamper-Evident Audit Trail:** Verify officer corrections are appended with sequential Merkle entry hashes.
- [ ] **Statutory Certificate:** Verify `GET /api/v1/inspections/{id}/evidence/certificate` outputs a complete certificate under Section 63 of Bharatiya Sakshya Adhiniyam, 2023 / Section 65B of Indian Evidence Act, 1872.
- [ ] **Legal Disclaimers:** Confirm generated PDF reports and JSON exports contain the mandatory, un-omittable statutory disclaimer (`_legal_disclaimer.html`).

### 3.4 SRE, Observability & Incident Response
- [ ] **Scraper Health:** Verify Prometheus targets are scraping `https://<API_HOST>/metrics` every 15s.
- [ ] **Grafana Dashboard:** Verify `monitoring/grafana/dashboards/niyamdrishti_overview.json` displays active requests, P95 latencies, compliance verdict distributions, and offline sync counts.
- [ ] **Alerting Rules:** Confirm alerts for API downtime (`NiyamDrishtiDown`), high 5xx error rate (`High5xxErrorRate` > 5%), and elevated P95 latency (`HighP95Latency` > 3s).
- [ ] **Database Connection Resilience:** Verify Neon pool parameters (`pool_pre_ping=True`, `pool_recycle=300s`) recover automatically from serverless idle scale-to-zero.

