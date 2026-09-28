# NiyamDrishti Officer App

This directory contains the shared officer application for NiyamDrishti. The same Next.js frontend is delivered as an installable web app and packaged as an Android APK with Capacitor; it is not a separate native UI.

## What it handles

- Guided package-evidence capture and capture-quality feedback.
- Local inspection storage and an officer-controlled sync queue.
- Android on-device ML Kit text recognition and barcode decoding.
- A clearly separated **local provisional evidence** state for offline captures.
- Server-backed inspection results, evidence overlays, review, reports, history, and analytics.

Offline recognition stores raw text, barcode values, and image geometry on the device. It does not create a legal pass/fail result. The officer chooses **Sync Now** when connectivity is available; the server then processes the original evidence and produces the verified inspection result.

## Local development

```powershell
npm install
npm run dev
```

Open `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL` in `.env.local` when using a local API:

```text
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Checks

```powershell
npm run lint
npm run build
```

## Android

```powershell
npm run android:sync
npm run android:open
```

`android:sync` creates the static web bundle and copies it into the Capacitor Android project. Android Studio is then used to run, test, or sign the APK. Generated APKs, Android Studio settings, device captures, and local databases must stay out of Git; publish a tested demo build through a GitHub Release instead.

## Data boundaries

Do not place inspection images, API keys, `.env.local`, local IndexedDB exports, OCR diagnostics, or model files in this directory's tracked source. Dataset methodology and the reusable Label Studio tooling live in [`../tools/label_studio`](../tools/label_studio).
