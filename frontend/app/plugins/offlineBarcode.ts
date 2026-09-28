"use client";

import { Capacitor } from "@capacitor/core";
import { nativeOfflineOcr } from "./offlineOcr";

export interface OfflineBarcodeBox {
  x: number;
  y: number;
  w: number;
  h: number;
  polygon: [number, number][];
  coordinateSpace: "source_image_px";
}

export interface OfflineBarcode {
  /** Exact value decoded by ML Kit. It can be an EAN, UPC, Code 128, or other supported retail code. */
  rawValue: string;
  displayValue: string | null;
  /** ML Kit's numeric format constant; no legal inference is made from it. */
  format: number;
  boundingBox: OfflineBarcodeBox;
}

export interface OfflineBarcodeResult {
  sourceWidth: number;
  sourceHeight: number;
  barcodes: OfflineBarcode[];
}

interface OfflineBarcodeNativePlugin {
  isBarcodeAvailable(): Promise<{ available: boolean; mode: "bundled" }>;
  recognizeBarcodes(options: { dataUrl: string }): Promise<OfflineBarcodeResult>;
}

// Barcode decoding shares the already registered, bundled Android ML Kit bridge
// with raw text OCR, while retaining an independent TypeScript contract.
const nativeOfflineBarcode = nativeOfflineOcr as unknown as OfflineBarcodeNativePlugin;

/** True only for the bundled Android APK; the browser PWA remains unaffected. */
export function canUseOfflineBarcode(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.getPlatform() === "android";
}

/** Verifies that the packaged Android barcode bridge and its bundled model loaded. */
export async function getOfflineBarcodeAvailability(): Promise<boolean> {
  if (!canUseOfflineBarcode()) return false;
  const availability = await nativeOfflineBarcode.isBarcodeAvailable();
  return availability.available;
}

/** Returns decoded barcode values with exact source-image-pixel geometry. */
export async function recognizeOfflineBarcodes(dataUrl: string): Promise<OfflineBarcodeResult> {
  if (!canUseOfflineBarcode()) {
    throw new Error("On-device barcode scanning is available only in the Android APK.");
  }
  if (!(await getOfflineBarcodeAvailability())) {
    throw new Error("The bundled offline barcode scanner is unavailable.");
  }
  return nativeOfflineBarcode.recognizeBarcodes({ dataUrl });
}
