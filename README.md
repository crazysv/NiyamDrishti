# NiyamDrishti

[![CI](https://github.com/crazysv/NiyamDrishti/actions/workflows/ci.yml/badge.svg)](https://github.com/crazysv/NiyamDrishti/actions/workflows/ci.yml)

**Evidence-backed inspection support for packaged commodities under the Legal Metrology (Packaged Commodities) Rules, 2011.**

NiyamDrishti helps a Legal Metrology officer capture package-label evidence, extract important declarations, and review them against a versioned rule pack. Instead of returning an unexplained answer, the system connects each extracted declaration and finding to the image region that produced it.

It is built for field conditions: an Android officer can save a capture without connectivity, read locally detected text and barcodes, and decide when to manually sync it for server-side analysis.

> NiyamDrishti is decision-support software. It does not replace an officer's judgement or make a final legal determination from offline evidence.

## The problem

Package checks are often performed by manually reading small-print labels and comparing them with a dense rulebook. This is slow, difficult to audit, and can vary between officers. NiyamDrishti structures that workflow around evidence: capture the panels, identify declarations, evaluate the applicable versioned rules, and retain an inspection record that can be reviewed later.

## What the current build does

- Captures front, back, side, MRP-sticker, and listing-image evidence.
- Checks capture quality before processing, including blur, glare, framing, resolution, and occlusion signals.
- Extracts declarations such as product name, net quantity, MRP, manufacturing/packing date, manufacturer or packer details, consumer-care details, country of origin, and barcode.
- Draws evidence overlays on the original image and routes uncertain findings for officer review.
- Keeps rule logic in versioned JSON rule packs rather than hard-coding legal thresholds into screens.
- Generates inspection reports and keeps an inspection archive with review history.
- Provides an installable PWA and an Android APK built from the same frontend source.
- Preserves offline Android captures locally. Bundled ML Kit text recognition and barcode scanning create **local provisional evidence** without a network request or API quota use.
- Keeps queued offline captures local until the officer explicitly chooses **Sync Now**. Server processing then produces the authoritative inspection result.

## How the system works

```text
Officer captures package panels
        |
        +-- Android offline path
        |     ML Kit OCR + barcode scan
        |     local image + raw evidence saved on device
        |     provisional evidence shown; no legal verdict
        |
        +-- Officer-triggered online path
              FastAPI processing service
              OCR / extraction / versioned rule-pack evaluation
              evidence overlays + review queue + report
```

The online pipeline can use Gemini Vision OCR when configured, with local PaddleOCR and Tesseract paths available in the backend. Gemini is used for image understanding in the online flow; it is not required for offline capture storage or on-device provisional evidence.

## Dataset and evaluation approach

There is no ready-made labelled dataset for this exact Indian packaged-commodity inspection problem, so the team created a small, reviewed benchmark for development and evaluation.

- **Reviewed benchmark:** 73 training images with 225 reviewed boxes, and 18 product-disjoint validation images with 58 reviewed boxes.
- **Holdout:** 4 separate products / 12 images are kept out of training and tuning.
- **Fields:** product name, net quantity, MRP, manufacturing/packing date, manufacturer or packer, consumer care, country of origin, and barcode.
- **Annotation process:** Label Studio is used to review field labels and tight source-image rectangles. Local PaddleOCR predictions are only suggestions; reviewed boxes are the ground truth.
- **Supplemental set:** the team also assembled 1,007 local supplemental package images. After basic file and resolution checks, 441 were used only for local OCR/detector diagnostics. They were not silently treated as ground truth.

The raw images, annotations, model checkpoints, OCR outputs, and generated overlays are intentionally not published in this repository. They include team-provided and supplemental product imagery that is not appropriate to redistribute without clear source rights. The repository includes the reproducible Label Studio configuration, evaluation scripts, and a non-image [dataset manifest](tools/label_studio/dataset_manifest.example.json) so the methodology can be inspected without publishing the images.

The current detector work is experimental development tooling, not the basis for a claim of final legal or production accuracy. The released offline APK relies on ML Kit OCR and barcode detection for raw provisional evidence; the officer-triggered server workflow remains the final compliance-analysis path.

## Technology

| Area | Stack |
|---|---|
| Officer app | Next.js, React, TypeScript, Tailwind CSS, Dexie/IndexedDB |
| Android packaging | Capacitor, Camera, Filesystem, App plugins |
| Offline recognition | Bundled Google ML Kit Text Recognition and Barcode Scanning |
| Server API | FastAPI, SQLAlchemy, Alembic, Pydantic |
| Online OCR | Gemini Vision OCR when configured; PaddleOCR and Tesseract support in the backend |
| Rule evaluation | Versioned JSON rule packs and Python rules engine |
| Development tooling | Label Studio, local PaddleOCR evaluation scripts, Docker |

## Repository layout

```text
frontend/                Next.js app, PWA, and Capacitor Android project
backend/                 FastAPI API, OCR/extraction pipeline, rule engine, reports, tests
tools/label_studio/      Annotation configuration, dataset metadata, and evaluation tools
docker/                  Local Docker Compose environment
monitoring/              Prometheus and Grafana configuration
```

## Run locally

### Prerequisites

- Node.js 20+
- Python 3.11+
- Android Studio, only when building the APK
- Tesseract OCR, only when using the backend fallback OCR locally

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

The API runs at `http://localhost:8000`; OpenAPI documentation is available at `http://localhost:8000/docs`.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. To use the local API, set `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` in `frontend/.env.local`.

### Android APK

```powershell
cd frontend
npm install
npm run android:sync
npm run android:open
```

Build a debug or signed release APK from Android Studio. Do not commit generated APK files; publish a tested release build as a [GitHub Release](https://github.com/crazysv/NiyamDrishti/releases) asset instead.

## Validation

```powershell
# Frontend
cd frontend
npm run lint
npm run build

# Backend
cd backend
python -m ruff check app tests
python -m pytest -q
```

## Security and data handling

- Do not commit `.env` files, API keys, inspection images, local databases, models, or generated reports.
- Offline captures stay on the device until an officer chooses to sync.
- A server-generated result is not merged with or replaced by an offline provisional result.
- Legal citations and rule-pack changes require verification before production use.

## Project status

This is a Smart India Hackathon 2026 prototype for SIH26034. It demonstrates the inspection workflow, evidence mapping, review path, offline capture resilience, and a transparent approach to building a domain-specific benchmark. A real deployment would still require formal legal validation, security review, retention policy approval, and a pilot with authorised field data.
