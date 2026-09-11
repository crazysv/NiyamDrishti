export interface NormalizedOcrImage {
  /** Canonical, upright JPEG used by quality checks, sync, server OCR and evidence. */
  dataUrl: string;
  width: number;
  height: number;
  originalWidth: number;
  originalHeight: number;
  byteSize: number;
}

const MAX_UPLOAD_BYTES = 420 * 1024;
const INITIAL_EDGE = 1280;
const MIN_EDGE = 640;

export function estimateDataUrlBytes(dataUrl: string): number {
  const encoded = dataUrl.split(",", 2)[1] || "";
  return Math.ceil((encoded.length * 3) / 4);
}

function loadImage(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Unable to prepare the captured photo."));
    image.src = dataUrl;
  });
}

/**
 * Draws the browser-decoded image once onto a canvas. This applies EXIF
 * orientation from gallery uploads and strips the orientation tag, so every
 * downstream coordinate is measured against the exact upright JPEG displayed
 * to the officer and stored by the API.
 */
export async function normalizeImageForOcr(dataUrl: string): Promise<NormalizedOcrImage> {
  const image = await loadImage(dataUrl);
  const originalWidth = image.naturalWidth;
  const originalHeight = image.naturalHeight;
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context || originalWidth < 1 || originalHeight < 1) {
    throw new Error("Unable to create a normalized OCR image.");
  }

  let maxEdge = INITIAL_EDGE;
  let quality = 0.82;
  let encoded = "";
  let width = originalWidth;
  let height = originalHeight;

  for (let attempt = 0; attempt < 6; attempt += 1) {
    const scale = Math.min(1, maxEdge / Math.max(originalWidth, originalHeight));
    width = Math.max(1, Math.round(originalWidth * scale));
    height = Math.max(1, Math.round(originalHeight * scale));
    canvas.width = width;
    canvas.height = height;
    context.drawImage(image, 0, 0, width, height);
    encoded = canvas.toDataURL("image/jpeg", quality);

    if (estimateDataUrlBytes(encoded) <= MAX_UPLOAD_BYTES || maxEdge <= MIN_EDGE) {
      return {
        dataUrl: encoded,
        width,
        height,
        originalWidth,
        originalHeight,
        byteSize: estimateDataUrlBytes(encoded),
      };
    }

    maxEdge = Math.max(MIN_EDGE, Math.round(maxEdge * 0.78));
    quality = Math.max(0.62, quality - 0.05);
  }

  return {
    dataUrl: encoded,
    width,
    height,
    originalWidth,
    originalHeight,
    byteSize: estimateDataUrlBytes(encoded),
  };
}
