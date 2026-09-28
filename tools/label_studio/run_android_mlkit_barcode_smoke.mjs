/**
 * Decode one local package image through the installed APK's bundled ML Kit
 * barcode bridge. This stays local: no product API, upload, Label Studio, or
 * inspection data is touched.
 *
 * Usage:
 *   node tools/label_studio/run_android_mlkit_barcode_smoke.mjs \
 *     test_data/benchmark_raw/babool_toothpaste/back.jpeg
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { basename, extname, resolve } from "node:path";
import process from "node:process";

const PACKAGE_NAME = "com.niyamdrishti.app";
const PORT = "9223";
const imagePath = resolve(process.argv[2] ?? "");

function adbPath() {
  if (!process.env.LOCALAPPDATA) throw new Error("LOCALAPPDATA is unavailable; cannot locate adb.");
  return `${process.env.LOCALAPPDATA}\\Android\\Sdk\\platform-tools\\adb.exe`;
}

function run(adb, args) {
  return execFileSync(adb, args, { encoding: "utf8" }).trim();
}

function firstConnectedDevice(adb) {
  const devices = run(adb, ["devices"])
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.trim().split(/\s+/))
    .filter((parts) => parts[1] === "device")
    .map((parts) => parts[0]);
  if (devices.length !== 1) throw new Error(`Expected one authorized USB device; found ${devices.length}.`);
  return devices[0];
}

function createEvaluator(socket) {
  let nextId = 0;
  const pending = new Map();
  socket.addEventListener("message", async (event) => {
    const payload = typeof event.data === "string" ? event.data : await event.data.text();
    const message = JSON.parse(payload);
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error || message.result?.exceptionDetails) {
      request.reject(new Error(message.error?.message || message.result.exceptionDetails.text));
    } else request.resolve(message.result?.result?.value);
  });
  return (expression) => new Promise((resolvePromise, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve: resolvePromise, reject });
    socket.send(JSON.stringify({
      id,
      method: "Runtime.evaluate",
      params: { expression, awaitPromise: true, returnByValue: true },
    }));
  });
}

async function main() {
  if (!existsSync(imagePath)) throw new Error(`Image does not exist: ${imagePath}`);
  const adb = adbPath();
  if (!existsSync(adb)) throw new Error(`adb does not exist: ${adb}`);
  const serial = firstConnectedDevice(adb);
  const deviceArgs = (...args) => ["-s", serial, ...args];

  // Reload the installed APK process so a just-installed native bridge cannot
  // be mistaken for the old in-memory WebView/native process.
  run(adb, deviceArgs("shell", "am", "force-stop", PACKAGE_NAME));
  run(adb, deviceArgs("shell", "monkey", "-p", PACKAGE_NAME, "1"));
  await new Promise((resolvePromise) => setTimeout(resolvePromise, 2000));
  const pid = run(adb, deviceArgs("shell", "pidof", PACKAGE_NAME)).split(/\s+/)[0];
  if (!pid) throw new Error("NiyamDrishti is not running on the connected device.");

  try { run(adb, deviceArgs("forward", "--remove", `tcp:${PORT}`)); } catch { /* no old port */ }
  run(adb, deviceArgs("forward", `tcp:${PORT}`, `localabstract:webview_devtools_remote_${pid}`));

  let socket;
  try {
    const targets = await fetch(`http://127.0.0.1:${PORT}/json`).then((response) => response.json());
    const target = targets.find((item) => item.type === "page" && item.url.includes("https://localhost"));
    if (!target?.webSocketDebuggerUrl) throw new Error("APK WebView target not found; keep the app open in the foreground.");
    socket = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolvePromise, reject) => {
      socket.addEventListener("open", resolvePromise, { once: true });
      socket.addEventListener("error", () => reject(new Error("Could not connect to APK WebView.")), { once: true });
    });
    const evaluate = createEvaluator(socket);
    const extension = extname(imagePath).toLowerCase() === ".png" ? "png" : "jpeg";
    const dataUrl = `data:image/${extension};base64,${readFileSync(imagePath).toString("base64")}`;
    const value = await evaluate(`(async () => JSON.stringify(await window.Capacitor.Plugins.OfflineOcr.recognizeBarcodes({ dataUrl: ${JSON.stringify(dataUrl)} })))()`);
    const output = JSON.parse(value);
    console.log(JSON.stringify({ image: basename(imagePath), device: serial, ...output }, null, 2));
    if (!output.barcodes?.length) process.exitCode = 2;
  } finally {
    socket?.close();
    try { run(adb, deviceArgs("forward", "--remove", `tcp:${PORT}`)); } catch { /* best effort */ }
  }
}

main().catch((error) => {
  console.error(`Barcode smoke test failed: ${error.message}`);
  process.exitCode = 1;
});
