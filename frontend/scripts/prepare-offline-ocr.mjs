import { cp, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const publicOcr = resolve(root, "public", "ocr");

await mkdir(resolve(publicOcr, "core"), { recursive: true });
await mkdir(resolve(publicOcr, "lang"), { recursive: true });

await cp(resolve(root, "node_modules", "tesseract.js", "dist", "worker.min.js"), resolve(publicOcr, "worker.min.js"));
for (const filename of [
  "tesseract-core.wasm.js",
  "tesseract-core-lstm.wasm.js",
  "tesseract-core-simd.wasm.js",
  "tesseract-core-simd-lstm.wasm.js",
]) {
  await cp(
    resolve(root, "node_modules", "tesseract.js-core", filename),
    resolve(publicOcr, "core", filename),
  );
}
await cp(
  resolve(root, "node_modules", "@tesseract.js-data", "eng", "4.0.0_best_int", "eng.traineddata.gz"),
  resolve(publicOcr, "lang", "eng.traineddata.gz"),
);
