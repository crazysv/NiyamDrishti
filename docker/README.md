# Local Dev — Docker Compose

## Services

| Service | URL | Notes |
|---|---|---|
| FastAPI API | http://localhost:8000 | Hot-reload enabled |
| API docs (Swagger) | http://localhost:8000/docs | Auto-generated |
| PostgreSQL | localhost:5432 | user: niyam / pass: niyam |
| MinIO (R2 stand-in) | http://localhost:9000 | S3-compatible |
| MinIO console | http://localhost:9001 | minioadmin / minioadmin |

## Commands

`ash
# Start everything (first run — builds the API image)
docker compose up --build

# Start in background
docker compose up -d

# View API logs
docker compose logs -f api

# Stop and remove containers (keeps data volumes)
docker compose down

# Full reset including volumes (wipes DB + MinIO data)
docker compose down -v
`

## SQLite vs Postgres for local dev

The compose stack uses Postgres (matching Neon in production).
If you prefer pure SQLite locally (no Docker needed):

`ash
cd backend
cp .env.example .env
# Edit .env: DATABASE_URL=sqlite+aiosqlite:///./niyamdrishti.db
uvicorn app.main:app --reload
`

The backend switches automatically based on DATABASE_URL — no code change needed.
