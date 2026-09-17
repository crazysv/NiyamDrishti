# NiyamDrishti Label Studio workspace

This workspace creates reviewed ground truth for statutory package declarations. It is for **evaluation first**, not model training. Do not import `benchmark_holdout`; those images are reserved for final testing and the demo.

## Start locally

1. Generate the task manifest from the raw benchmark images:

   ```powershell
   .\tools\label_studio\generate_tasks.ps1
   ```

2. Start Docker Desktop, then run:

   ```powershell
   .\tools\label_studio\run_label_studio.ps1
   ```

3. Open `http://localhost:8080`, create a local account, then create a project named **NiyamDrishti — Indian Package Declarations**.
4. In **Labeling Setup**, choose **Custom Template** and paste `label_config.xml`.
5. In **Data Import**, upload `test_data/label_studio/tasks_raw.json`.
6. In **Settings → Cloud Storage**, add a **Source Storage → Local Files** entry with path `/label-studio/files/benchmark_raw`. This is a required read-only permission record for Label Studio's local-image route; do **not** sync it, because the task manifest has already created the 92 tasks.
7. Before reviewing model suggestions, in **Settings → Annotation**, enable **Use predictions to pre-label tasks**. Without this setting, saved predictions are intentionally hidden in the labeling view.

The images are served read-only from `test_data/benchmark_raw`; Label Studio annotation state is stored locally at `test_data/label_studio/state` and is deliberately ignored by Git. The launcher sets Label Studio's `LOCAL_FILES_SERVING_ENABLED` and `LOCAL_FILES_DOCUMENT_ROOT` settings so the imported local-file URLs resolve inside Docker.

## Local PaddleOCR pre-labels

Use the project’s existing local PaddleOCR and declaration extractors to create **review-only predictions** before manual labeling. This uses no Gemini key or quota.

```powershell
# Smoke-test one image first.
& .\backend\.venv\Scripts\python.exe .\tools\label_studio\prelabel_local_paddle.py --limit 1

# Create all predictions locally (does not change Label Studio yet).
& .\backend\.venv\Scripts\python.exe .\tools\label_studio\prelabel_local_paddle.py
```

To attach the generated predictions to the existing tasks, create a Label Studio personal access token in the local account settings, set it only in the current PowerShell session, then run the `--apply` command. `--replace` removes only prior predictions made by this same local-Paddle tool; it never deletes officer annotations.

```powershell
$env:LABEL_STUDIO_API_TOKEN = '<local Label Studio token>'
& .\backend\.venv\Scripts\python.exe .\tools\label_studio\prelabel_local_paddle.py --apply --replace
```

If attaching was interrupted after the prediction file was created, reuse that file rather than running OCR again:

```powershell
& .\backend\.venv\Scripts\python.exe .\tools\label_studio\prelabel_local_paddle.py --reuse-output --apply --replace
```

Paddle predictions are suggestions, not ground truth: review their field labels, box placement, and barcode result before submitting an annotation. The bridge deliberately omits obvious website/contact false product names and QR/non-EAN barcode detections; add a genuine omitted declaration manually. It groups nearby same-field OCR lines into one field-level suggestion (for example, the complete consumer-care contact block) and adds a small boundary padding; it does not overwrite an officer annotation.

## Visual QA sweep

Render a complete set of overlay contact sheets before or after a pre-label run:

```powershell
& .\backend\.venv\Scripts\python.exe .\tools\label_studio\render_prediction_overlays.py
```

The eight local contact sheets are written to `tmp/label_studio_overlay_audit/`. They are ignored by Git and let the team quickly spot an off-target or overly broad suggestion before reviewing it in Label Studio.

## Annotation rules

- One tight rectangle per visible statutory declaration.
- The first review pass is **box-first**: transcriptions and readability are optional, so a reviewer can submit after verifying the field label and rectangle. The imported Paddle prediction retains its provisional OCR text separately.
- If you add a transcription, copy the text exactly as shown; never "fix" spelling, OCR, or punctuation.
- Do not annotate logos, marketing slogans, nutrition tables, or generic paragraphs unless they contain one of the listed statutory fields.
- For a declaration split across nearby lines, draw one rectangle that covers only that declaration. Add the full joined transcription only when it is quick to verify.
- When useful, mark a field `partly_obscured` or `unreadable` rather than guessing.
- `barcode` needs a box; its printed number is optional in this first pass.
