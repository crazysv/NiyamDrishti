"use client";

import { useEffect } from "react";

/** Registers the PWA worker so the app shell remains available for offline capture. */
export default function OfflineRuntime() {
  useEffect(() => {
    async function register() {
      if (!("serviceWorker" in navigator)) return;
      try {
        const registration = await navigator.serviceWorker.register("/service-worker.js?v=7");
        await registration.update();
      } catch (error) {
        console.warn("PWA service worker could not be registered:", error);
      }
    }
    register();
  }, []);

  return null;
}
