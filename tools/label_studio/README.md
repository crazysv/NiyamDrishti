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

The images are served read-only from `test_data/benchmark_raw`; Label Studio annotation state is stored locally at `test_data/label_studio/state` and is deliberately ignored by Git. The launcher sets Label Studio's `LOCAL_FILES_SERVING_ENABLED` and `LOCAL_FILES_DOCUMENT_ROOT` settings so the imported local-file URLs resolve inside Docker.

## Annotation rules

- One tight rectangle per visible statutory declaration.
- Transcribe the text exactly as shown; never "fix" spelling, OCR, or punctuation.
- Do not annotate logos, marketing slogans, nutrition tables, or generic paragraphs unless they contain one of the listed statutory fields.
- For a declaration split across nearby lines, draw one rectangle that covers only that declaration and enter the full joined transcription.
- Mark a field `partly_obscured` or `unreadable` rather than guessing.
- `barcode` needs a box but no semantic transcription. Enter the printed barcode number when it is visible; otherwise enter `unreadable`.
