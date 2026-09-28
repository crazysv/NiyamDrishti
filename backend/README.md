# NiyamDrishti API

This directory contains the FastAPI service behind NiyamDrishti. It accepts inspection evidence, runs the configured online extraction pipeline, evaluates versioned rule packs, stores traceable evidence, and returns the server-verified inspection result used by the web app and Android APK.

The service is an inspection-support system, not a substitute for an officer's legal judgement. Rules are kept as versioned data and uncertain extraction must remain reviewable rather than being presented as a definitive conclusion.

## Responsibilities

- Inspection, evidence, review, report, history, and analytics APIs.
- Online OCR and structured extraction with Gemini Vision when configured.
- Local PaddleOCR and Tesseract support for development and fallback paths.
- Versioned Legal Metrology rule-pack evaluation and evidence-linked findings.
- SQLAlchemy persistence, Alembic migrations, and PDF report generation.

Android offline ML Kit OCR and barcode decoding run on the device. A queued capture is only processed here after the officer explicitly asks to sync it.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`; interactive OpenAPI documentation is at `http://localhost:8000/docs`.

## Configuration

Start from `.env.example`. Keep real keys only in your local `.env` or the deployment environment. Never commit API keys, database files, generated reports, uploaded images, OCR output, or model checkpoints.

When Gemini is configured, it is an online processing provider only. Offline capture storage, on-device OCR, and barcode detection do not require it or consume its quota.

## Validation

```powershell
python -m ruff check app tests
python -m pytest -q
```

## Deployment note

The repository supports local Docker development and cloud deployment configuration, but it does not claim a production or legally certified deployment. Before a real field rollout, validate the active rule pack and citations, secure the deployment secrets and data-retention policy, complete a security review, and pilot with authorised data.
