"use client";

import { useEffect } from "react";
import { Capacitor } from "@capacitor/core";
import { App } from "@capacitor/app";
import { getOfflineBarcodeAvailability } from "@/app/plugins/offlineBarcode";
import { getOfflineOcrAvailability } from "@/app/plugins/offlineOcr";

/** Registers the PWA worker so the app shell remains available for offline capture. */
export default function OfflineRuntime() {
  useEffect(() => {
    async function register() {
      try {
        // Android already ships its entire app shell inside the APK. A browser
        // service worker can otherwise serve a stale JavaScript bundle after an
        // APK update, so explicitly remove any PWA worker/cache in that runtime.
        if (Capacitor.isNativePlatform()) {
          if ("serviceWorker" in navigator) {
            const registrations = await navigator.serviceWorker.getRegistrations();
            await Promise.all(registrations.map((registration) => registration.unregister()));
          }
          if ("caches" in window) {
            const cacheNames = await caches.keys();
            await Promise.all(
              cacheNames
                .filter((name) => name.startsWith("niyamdrishti-offline-"))
                .map((name) => caches.delete(name))
            );
          }
          try {
            const available = await getOfflineOcrAvailability();
            console.info(`[OfflineOCR] Bundled Android ML Kit available: ${available}`);
          } catch (error) {
            console.error("[OfflineOCR] Bundled Android ML Kit unavailable:", error);
          }
          try {
            const available = await getOfflineBarcodeAvailability();
            console.info(`[OfflineBarcode] Bundled Android ML Kit available: ${available}`);
          } catch (error) {
            console.error("[OfflineBarcode] Bundled Android ML Kit unavailable:", error);
          }
          return;
        }

        if (!("serviceWorker" in navigator)) return;

        const registration = await navigator.serviceWorker.register("/service-worker.js?v=8");
        await registration.update();
      } catch (error) {
        console.warn("PWA service worker could not be registered:", error);
      }
    }
    register();
  }, []);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;

    let removed = false;
    let listener: { remove: () => Promise<void> } | null = null;

    async function registerNativeBackHandler() {
      listener = await App.addListener("backButton", () => {
        const path = window.location.pathname;

        // Capture is the APK's start screen. Android's normal behaviour is to
        // leave the app only from this root—not from an evidence, review,
        // report, history, or admin detail route.
        if (path === "/") {
          void App.exitApp();
          return;
        }

        if (window.history.length > 1) {
          window.history.back();
          return;
        }

        // A detail screen can be opened directly from a notification, link,
        // or restored Android activity without browser history. Keep the
        // officer inside the app in that case.
        window.location.assign(path.startsWith("/inspections") || path.startsWith("/admin") ? "/history" : "/");
      });

      if (removed) {
        await listener.remove();
      }
    }

    void registerNativeBackHandler();
    return () => {
      removed = true;
      void listener?.remove();
    };
  }, []);

  return null;
}
