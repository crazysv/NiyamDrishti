/**
 * Run frozen raw benchmark images through the installed Android APK's bundled
 * ML Kit bridge. This is deliberately a device diagnostic: it writes raw OCR
 * text and source-image geometry locally and never calls the product API,
 * edits Label Studio, or creates an inspection.
 *
 * Prerequisites: an unlocked USB-debuggable phone running the debug APK.
 * Usage: node tools/label_studio/run_android_mlkit_benchmark.mjs
 */

import { execFileSync } from "node:child_process";
import { readFileSync, existsSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import process from "node:process";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const RAW_ROOT = join(ROOT, "test_data", "benchmark_raw");
const GROUND_TRUTH = join(ROOT, "test_data", "label_studio", "exports", "ground_truth_v1.json");
const DEFAULT_OUTPUT = join(ROOT, "test_data", "label_studio", "reports", "android_mlkit_raw_ocr.json");
const PACKAGE_NAME = "com.niyamdrishti.app";
const LOCAL_PORT = "9222";

function parseArgs(argv) {
  const options = { output: DEFAULT_OUTPUT, limit: undefined, device: undefined };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--output") options.output = resolve(argv[++index] ?? "");
    else if (value === "--limit") options.limit = Number(argv[++index]);
    else if (value === "--device") options.device = argv[++index];
    else if (value === "--help") {
      console.log("Usage: node tools/label_studio/run_android_mlkit_benchmark.mjs [--device SERIAL] [--limit N] [--output FILE]");
      process.exit(0);
    } else throw new Error(`Unknown argument: ${value}`);
  }
  if (options.limit !== undefined && (!Number.isInteger(options.limit) || options.limit < 1)) {
    throw new Error("--limit must be a positive integer.");
  }
  return options;
}

function adbPath() {
  const localAppData = process.env.LOCALAPPDATA;
  if (!localAppData) throw new Error("LOCALAPPDATA is not set; cannot locate adb.");
  return join(localAppData, "Android", "Sdk", "platform-tools", "adb.exe");
}

function adb(adbExecutable, serial, args) {
  return execFileSync(adbExecutable, serial ? ["-s", serial, ...args] : args, { encoding: "utf8" }).trim();
}

function connectedDevice(adbExecutable, requestedSerial) {
  const lines = adb(adbExecutable, undefined, ["devices", "-l"]).split(/\r?\n/).slice(1);
  const connected = lines
    .map((line) => line.trim().split(/\s+/))
    .filter((parts) => parts.length >= 2 && parts[1] === "device")
    .map((parts) => parts[0]);
  if (requestedSerial) {
    if (!connected.includes(requestedSerial)) throw new Error(`Requested device ${requestedSerial} is not authorized and connected.`);
    return requestedSerial;
  }
  if (connected.length !== 1) throw new Error(`Expected exactly one authorized Android device, found ${connected.length}. Use --device SERIAL.`);
  return connected[0];
}

function waitForWebSocket(url) {
  return new Promise((resolvePromise, reject) => {
    const socket = new WebSocket(url);
    const timeout = setTimeout(() => {
      socket.close();
      reject(new Error("Timed out connecting to Android WebView DevTools."));
    }, 15_000);
    socket.addEventListener("open", () => {
      clearTimeout(timeout);
      resolvePromise(socket);
    }, { once: true });
    socket.addEventListener("error", () => {
      clearTimeout(timeout);
      reject(new Error("Could not connect to Android WebView DevTools. Open the APK first."));
    }, { once: true });
  });
}

function evaluator(socket) {
  let id = 0;
  const pending = new Map();
  socket.addEventListener("message", async (event) => {
    const payload = typeof event.data === "string" ? event.data : await event.data.text();
    const message = JSON.parse(payload);
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else if (message.result?.exceptionDetails) request.reject(new Error(message.result.exceptionDetails.text || "WebView evaluation failed."));
    else request.resolve(message.result?.result?.value);
  });
  return (expression, timeoutMs = 120_000) => new Promise((resolvePromise, reject) => {
    const requestId = ++id;
    const timeout = setTimeout(() => {
      pending.delete(requestId);
      reject(new Error(`Timed out after ${timeoutMs / 1000}s waiting for device OCR.`));
    }, timeoutMs);
    pending.set(requestId, {
      resolve(value) { clearTimeout(timeout); resolvePromise(value); },
      reject(error) { clearTimeout(timeout); reject(error); },
    });
    socket.send(JSON.stringify({
      id: requestId,
      method: "Runtime.evaluate",
      params: { expression, awaitPromise: true, returnByValue: true },
    }));
  });
}

function taskKey(task) {
  const data = task?.data;
  if (!data?.sample_id || !data?.source_filename) return null;
  return { sampleId: String(data.sample_id), sourceFilename: String(data.source_filename) };
}

function latestAnnotation(task) {
  const annotations = Array.isArray(task.annotations) ? task.annotations : [];
  return annotations.length ? annotations.at(-1) : null;
}

function normalizeAndRecognizeExpression(dataUrl) {
  return `
    (async () => {
      const input = ${JSON.stringify(dataUrl)};
      const image = await new Promise((resolve, reject) => {
        const element = new Image();
        element.onload = () => resolve(element);
        element.onerror = () => reject(new Error("Benchmark image could not decode in the APK WebView."));
        element.src = input;
      });
      const originalWidth = image.naturalWidth;
      const originalHeight = image.naturalHeight;
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d");
      if (!context || originalWidth < 1 || originalHeight < 1) throw new Error("Could not normalize benchmark image.");
      let maxEdge = 1280;
      let quality = 0.82;
      let normalized = "";
      let width = originalWidth;
      let height = originalHeight;
      for (let attempt = 0; attempt < 6; attempt += 1) {
        const scale = Math.min(1, maxEdge / Math.max(originalWidth, originalHeight));
        width = Math.max(1, Math.round(originalWidth * scale));
        height = Math.max(1, Math.round(originalHeight * scale));
        canvas.width = width;
        canvas.height = height;
        context.drawImage(image, 0, 0, width, height);
        normalized = canvas.toDataURL("image/jpeg", quality);
        const bytes = Math.ceil(((normalized.split(",", 2)[1] || "").length * 3) / 4);
        if (bytes <= 420 * 1024 || maxEdge <= 640) break;
        maxEdge = Math.max(640, Math.round(maxEdge * 0.78));
        quality = Math.max(0.62, quality - 0.05);
      }
      const result = await window.Capacitor.Plugins.OfflineOcr.recognize({ dataUrl: normalized });
      return JSON.stringify({ originalWidth, originalHeight, normalizedWidth: width, normalizedHeight: height, result });
    })()
  `;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const adbExecutable = adbPath();
  if (!existsSync(adbExecutable)) throw new Error(`adb was not found at ${adbExecutable}`);
  const serial = connectedDevice(adbExecutable, options.device);
  let pid = "";
  try { pid = adb(adbExecutable, serial, ["shell", "pidof", PACKAGE_NAME]); } catch { /* launch below */ }
  if (!pid) {
    adb(adbExecutable, serial, ["shell", "monkey", "-p", PACKAGE_NAME, "1"]);
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 3_000));
    try { pid = adb(adbExecutable, serial, ["shell", "pidof", PACKAGE_NAME]); } catch { /* reported below */ }
  }
  if (!pid) throw new Error("The NiyamDrishti APK could not be started on the connected phone.");

  try { adb(adbExecutable, serial, ["forward", "--remove", `tcp:${LOCAL_PORT}`]); } catch { /* no previous diagnostic forward */ }
  adb(adbExecutable, serial, ["forward", `tcp:${LOCAL_PORT}`, `localabstract:webview_devtools_remote_${pid.trim().split(/\s+/)[0]}`]);

  let socket;
  try {
    const targets = await fetch(`http://127.0.0.1:${LOCAL_PORT}/json`).then((response) => response.json());
    const target = targets.find((item) => item.type === "page" && item.url.includes("https://localhost"));
    if (!target?.webSocketDebuggerUrl) throw new Error("NiyamDrishti WebView target was not found. Keep the APK in the foreground.");
    socket = await waitForWebSocket(target.webSocketDebuggerUrl);
    const evaluate = evaluator(socket);
    const bridge = JSON.parse(await evaluate("JSON.stringify({offline: typeof window.Capacitor?.Plugins?.OfflineOcr})"));
    if (bridge.offline !== "object") throw new Error("The installed APK does not expose the OfflineOcr bridge. Install the current debug APK first.");

    const tasks = JSON.parse(readFileSync(GROUND_TRUTH, "utf8"));
    const selected = tasks.filter((task) => taskKey(task) && latestAnnotation(task)?.result?.length);
    const work = options.limit ? selected.slice(0, options.limit) : selected;
    const records = [];
    const startedAt = new Date().toISOString();
    for (const [index, task] of work.entries()) {
      const key = taskKey(task);
      const imagePath = join(RAW_ROOT, key.sampleId, key.sourceFilename);
      if (!existsSync(imagePath)) throw new Error(`Missing raw benchmark image: ${imagePath}`);
      const extension = key.sourceFilename.toLowerCase().endsWith(".png") ? "png" : "jpeg";
      const dataUrl = `data:image/${extension};base64,${readFileSync(imagePath).toString("base64")}`;
      console.log(`ML Kit starting [${index + 1}/${work.length}] ${key.sampleId}/${key.sourceFilename}`);
      const value = await evaluate(normalizeAndRecognizeExpression(dataUrl));
      const output = JSON.parse(value);
      records.push({ sample_id: key.sampleId, source_filename: key.sourceFilename, image_role: task.data.image_role, ...output });
      console.log(`ML Kit [${index + 1}/${work.length}] ${key.sampleId}/${key.sourceFilename}: ${output.result.lines.length} lines`);
    }
    const report = {
      generated_at: new Date().toISOString(),
      started_at: startedAt,
      device_serial: serial,
      package_name: PACKAGE_NAME,
      bridge: "OfflineOcr bundled ML Kit Latin",
      normalization: "Same canvas normalization parameters as frontend/app/utils/ocrImage.ts",
      source: { ground_truth: GROUND_TRUTH, raw_root: RAW_ROOT },
      task_count: records.length,
      records,
    };
    writeFileSync(options.output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    console.log(`Wrote ${options.output}`);
  } finally {
    socket?.close();
    try { adb(adbExecutable, serial, ["forward", "--remove", `tcp:${LOCAL_PORT}`]); } catch { /* best-effort cleanup */ }
  }
}

main().catch((error) => {
  console.error(`Android ML Kit benchmark failed: ${error.message}`);
  process.exitCode = 1;
});
