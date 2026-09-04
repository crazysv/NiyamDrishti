---
title: NiyamDrishti Legal Metrology Backend
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# NiyamDrishti Legal Metrology Inspection API

High-performance, court-ready automated compliance checking platform for the Legal Metrology (Packaged Commodities) Rules, 2011 (SIH26034).

## Deployment on Hugging Face Spaces

This backend is containerized to deploy natively on Hugging Face Spaces with Docker on the free `cpu-basic` tier (2 vCPU, 16 GB RAM).

### Environment Variables & Secrets
Configure these in your Hugging Face Space **Settings -> Variables and secrets**:
- `DATABASE_URL`: Neon Serverless PostgreSQL connection string
- `JWT_SECRET_KEY`: Secure cryptographic secret for signing officer session tokens
- `JWT_ALGORITHM`: `HS256`
- `APP_ENV`: `production`
- `CORS_ALLOWED_ORIGINS`: Allowed frontend URLs (e.g. `https://niyamdrishti.vercel.app,https://niyamdrishti.pages.dev,http://localhost:3000`)
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`: Cloudflare R2 object storage credentials

### API Probes
- `GET /health`: System and Neon database health probe
- `GET /health/live`: Container liveness probe
- `GET /docs`: Interactive OpenAPI documentation
