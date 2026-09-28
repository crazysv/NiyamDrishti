import {
  db,
  OfflineImage,
  OfflineLocalEvidence,
  OfflineLocalImageEvidence,
  saveLocalEvidence,
} from "@/app/db/dexie";
import {
  getOfflineOcrAvailability,
  recognizeOfflineImage,
} from "@/app/plugins/offlineOcr";
import {
  getOfflineBarcodeAvailability,
  recognizeOfflineBarcodes,
} from "@/app/plugins/offlineBarcode";

/**
 * Runs only inside the Android APK after a capture has safely entered the
 * offline queue. The output is intentionally raw evidence: this service never
 * assigns a declaration name, evaluates a rule, or returns a legal verdict.
 */
export async function createLocalProvisionalEvidence(
  inspectionId: string,
): Promise<OfflineLocalEvidence> {
  const images = await db.inspectionImages.where("inspectionId").equals(inspectionId).toArray();
  const now = new Date().toISOString();

  const [ocrAvailable, barcodeAvailable] = await Promise.allSettled([
    getOfflineOcrAvailability(),
    getOfflineBarcodeAvailability(),
  ]);
  const ocrEnabled = ocrAvailable.status === "fulfilled" && ocrAvailable.value;
  const barcodeEnabled = barcodeAvailable.status === "fulfilled" && barcodeAvailable.value;

  if (!ocrEnabled && !barcodeEnabled) {
    const unavailable: OfflineLocalEvidence = {
      id: inspectionId,
      inspectionId,
      status: "unavailable",
      engine: "mlkit_bundled",
      createdAt: now,
      updatedAt: now,
      images: [],
      error: "The bundled Android OCR and barcode services are unavailable on this device.",
    };
    await saveLocalEvidence(unavailable);
    return unavailable;
  }

  const processing: OfflineLocalEvidence = {
    id: inspectionId,
    inspectionId,
    status: "processing",
    engine: "mlkit_bundled",
    createdAt: now,
    updatedAt: now,
    images: [],
  };
  await saveLocalEvidence(processing);

  const evidenceImages: OfflineLocalImageEvidence[] = [];
  for (const image of images) {
    evidenceImages.push(await extractImageEvidence(image, ocrEnabled, barcodeEnabled));
  }

  const hasFailure = evidenceImages.some((image) => image.ocrError || image.barcodeError);
  const saved: OfflineLocalEvidence = {
    ...processing,
    status: hasFailure ? "partial" : "ready",
    updatedAt: new Date().toISOString(),
    images: evidenceImages,
  };
  await saveLocalEvidence(saved);
  return saved;
}

async function extractImageEvidence(
  image: OfflineImage,
  ocrEnabled: boolean,
  barcodeEnabled: boolean,
): Promise<OfflineLocalImageEvidence> {
  const sourceWidth = image.width || 0;
  const sourceHeight = image.height || 0;
  const result: OfflineLocalImageEvidence = {
    imageId: image.id,
    imageRole: image.imageRole,
    sourceWidth,
    sourceHeight,
    ocrText: "",
    ocrLines: [],
    barcodes: [],
  };

  if (ocrEnabled) {
    try {
      const ocr = await recognizeOfflineImage(image.dataUrl);
      result.sourceWidth = ocr.sourceWidth;
      result.sourceHeight = ocr.sourceHeight;
      result.ocrText = ocr.text;
      result.ocrLines = ocr.lines;
    } catch (error) {
      result.ocrError = errorMessage(error, "Local OCR could not process this image.");
    }
  } else {
    result.ocrError = "The bundled Android OCR service is unavailable.";
  }

  if (barcodeEnabled) {
    try {
      const barcode = await recognizeOfflineBarcodes(image.dataUrl);
      result.sourceWidth = barcode.sourceWidth || result.sourceWidth;
      result.sourceHeight = barcode.sourceHeight || result.sourceHeight;
      result.barcodes = barcode.barcodes;
    } catch (error) {
      result.barcodeError = errorMessage(error, "Local barcode scanning could not process this image.");
    }
  } else {
    result.barcodeError = "The bundled Android barcode service is unavailable.";
  }

  return result;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
