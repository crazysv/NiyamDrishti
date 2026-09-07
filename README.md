# NiyamDrishti

**AI-assisted, evidence-backed packaged-commodity inspection for Legal Metrology field teams.**

NiyamDrishti turns photographs of a package label into a structured, rule-by-rule inspection record. It extracts declarations such as MRP, net quantity, manufacture date, origin, manufacturer details, and consumer-care information; evaluates them against a versioned rule pack; and links each finding back to the source image.

> This is a decision-support tool. A field officer reviews low-confidence or incomplete findings before relying on them.

## What it does

- Captures front, back, side, MRP-sticker, and e-commerce evidence images.
- Runs quality checks before upload, including clarity, glare, framing, and legibility signals.
- Uses PaddleOCR with Tesseract fallback locally on the server; Gemini Vision OCR is an optional configured provider.
- Extracts statutory label declarations and evaluates data-driven rules—rule thresholds are kept in a versioned JSON rule pack, not embedded in UI code.
- Shows visual evidence overlays and a review queue for uncertain findings.
- Generates PDF compliance reports and maintains an inspection archive.
- Works as an installable PWA with offline capture storage, retryable uploads, and browser-based OCR support for prepared offline workflows.
- Provides a live supervisor analytics dashboard for inspection volume, compliance trends, rule hotspots, and officer throughput.

## Architecture

```text
Mobile PWA (Next.js)
  ├─ camera capture, IndexedDB queue, offline OCR runtime
  └─ evidence viewer, review, reports, analytics
            │
            ▼
FastAPI backend
  ├─ OCR and preprocessing
  ├─ declaration extraction and rules engine
  ├─ report generation and evidence verification
  └─ REST API
            │
            ▼
PostgreSQL / SQLite + object storage
```

## Technology

| Layer | Tools |
|---|---|
| Mobile/web app | Next.js, React, TypeScript, Tailwind CSS, Dexie/IndexedDB |
| API | FastAPI, SQLAlchemy, Alembic, Pydantic |
| OCR | PaddleOCR, Tesseract, optional Gemini Vision OCR |
| Rules | Versioned JSON rule packs and a Python rules engine |
| Development storage | SQLite and local filesystem |
| Production services | Render, Vercel, Neon PostgreSQL, Cloudflare R2 |

## Run locally

### Prerequisites

- Node.js 20+
- Python 3.11+
- Tesseract OCR installed and available on your `PATH` for local fallback OCR

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate              # Windows PowerShell
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

Set `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` in `frontend/.env.local` when running the frontend against the local API.

## Environment configuration

Start from [backend/.env.example](backend/.env.example). At minimum, configure a unique `JWT_SECRET_KEY` and an appropriate `CORS_ALLOWED_ORIGINS` value. Gemini OCR is optional; do not add any API keys to Git.

## Validation

```bash
# Frontend
cd frontend
npm run lint
npm run build

# Backend
cd backend
python -m ruff check app tests
python -m pytest -q
```

## Repository layout

```text
frontend/       Next.js PWA and mobile/supervisor user interfaces
backend/        FastAPI API, OCR pipeline, rule engine, reports, tests
docker/         Local Docker Compose environment and monitoring profile
monitoring/     Prometheus and Grafana configuration
test_data/      Repeatable OCR/calibration test inputs
```

## Privacy and repository policy

Detailed planning, decision, and operational documents are intentionally kept local and excluded from GitHub. Do not commit `.env` files, API keys, production evidence, local databases, generated reports, or captured inspection photos.

## Project status

The application currently supports capture, evidence mapping, review, reports, offline queueing, OCR provider selection, and live analytics. Production use should include a formal legal review, security review, data-retention policy, and validation against the applicable official rule pack.
