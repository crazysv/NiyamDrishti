export type OfflineOcrStatus = "checking" | "preparing" | "ready" | "unavailable";

const STORAGE_KEY = "niyamdrishti_offline_ocr_v3";
const EVENT_NAME = "niyamdrishti-offline-ocr-status";
let status: OfflineOcrStatus = "checking";

export function getOfflineOcrStatus(): OfflineOcrStatus {
  if (typeof window !== "undefined" && localStorage.getItem(STORAGE_KEY) === "ready") return "ready";
  return status;
}

export function setOfflineOcrStatus(next: OfflineOcrStatus): void {
  status = next;
  if (typeof window !== "undefined") {
    if (next === "ready") localStorage.setItem(STORAGE_KEY, "ready");
    if (next === "unavailable") localStorage.removeItem(STORAGE_KEY);
    window.dispatchEvent(new Event(EVENT_NAME));
  }
}

export function subscribeOfflineOcrStatus(callback: () => void): () => void {
  window.addEventListener(EVENT_NAME, callback);
  return () => window.removeEventListener(EVENT_NAME, callback);
}
