"use client";

import { Capacitor, registerPlugin } from "@capacitor/core";

export interface OfflineOcrBox {
  x: number;
  y: number;
  w: number;
  h: number;
  polygon: [number, number][];
  coordinateSpace: "source_image_px";
}

export interface OfflineOcrLine {
  text: string;
  boundingBox: OfflineOcrBox;
}

export interface OfflineOcrResult {
  text: string;
  sourceWidth: number;
  sourceHeight: number;
  lines: OfflineOcrLine[];
}

interface OfflineOcrNativePlugin {
  isAvailable(): Promise<{ available: boolean; script: "latin"; mode: "bundled" }>;
  recognize(options: { dataUrl: string }): Promise<OfflineOcrResult>;
}

/** Shared native bridge; barcode decoding extends it through a separate TS contract. */
export const nativeOfflineOcr = registerPlugin<OfflineOcrNativePlugin>("OfflineOcr");

/** True only inside the Android Capacitor APK; the browser PWA remains queue-only offline. */
export function canUseOfflineOcr(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.getPlatform() === "android";
}

/** Verifies that the packaged Android bridge and its bundled model loaded. */
export async function getOfflineOcrAvailability(): Promise<boolean> {
  if (!canUseOfflineOcr()) return false;
  const availability = await nativeOfflineOcr.isAvailable();
  return availability.available;
}

/**
 * Runs the bundled on-device OCR recognizer against an already-normalized,
 * upright image. This is intentionally raw OCR: field classification and rule
 * evaluation are introduced only after the benchmark validates them.
 */
export async function recognizeOfflineImage(dataUrl: string): Promise<OfflineOcrResult> {
  if (!canUseOfflineOcr()) {
    throw new Error("On-device OCR is available only in the Android APK.");
  }

  if (!(await getOfflineOcrAvailability())) {
    throw new Error("The bundled offline OCR model is unavailable.");
  }

  return nativeOfflineOcr.recognize({ dataUrl });
}
