"use client";

import { useEffect } from "react";
import { setOfflineOcrStatus } from "@/app/services/offlineOcrStatus";

/** Installs the same-origin cache that makes the packaged OCR runtime usable offline. */
export default function OfflineRuntime() {
  useEffect(() => {
    async function prepare() {
      if (!("serviceWorker" in navigator)) {
        setOfflineOcrStatus("unavailable");
        return;
      }
      if (!navigator.onLine) {
        setOfflineOcrStatus("unavailable");
        return;
      }
      try {
        setOfflineOcrStatus("preparing");
        // Query-version the worker so installed PWAs immediately adopt the
        // upload reliability release instead of an older cached client.
        const registration = await navigator.serviceWorker.register("/service-worker.js?v=6");
        await registration.update();
        await navigator.serviceWorker.ready;
        // Force the Next.js OCR chunk to be downloaded while connectivity exists.
        // The service worker retains every same-origin chunk it sees.
        await import("tesseract.js");
        setOfflineOcrStatus("ready");
      } catch (error) {
        console.warn("Offline OCR runtime could not be prepared:", error);
        setOfflineOcrStatus("unavailable");
      }
    }
    prepare();
  }, []);

  return null;
}
