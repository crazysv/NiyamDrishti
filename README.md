# NiyamDrishti

AI-assisted Legal Metrology label compliance inspection tool for field officers.

## Structure

| Directory | Purpose |
|---|---|
| /frontend | Next.js 14 PWA (TypeScript + Tailwind CSS) |
| /backend  | FastAPI (Python 3.11+) — OCR, rule engine, API |
| /docker   | Docker Compose for local development |
| /docs     | Full project documentation (PRD, tech spec, decisions, etc.) |
| /test_data| Spike test photos and results (Phase 0) |

## Quick start (local dev)

`ash
# Backend
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
`

See docs/00_README.md for the full documentation index.
See AGENTS.md for AI agent operating rules.
