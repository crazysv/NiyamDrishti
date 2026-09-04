/**
 * Client-Side Quality Gate for NiyamDrishti
 * Validates label photos before OCR to prevent wasted passes and provide
 * immediate, actionable retake feedback to the field officer (CAP-03..CAP-06).
 */

export type QualityIssueType =
  | "blur"
  | "glare"
  | "too_dark"
  | "low_resolution"
  | "perspective";

export interface QualityIssue {
  type: QualityIssueType;
  severity: "error" | "warning";
  title: string;
  message: string;
  actionHint: string;
}

export interface QualityMetrics {
  width: number;
  height: number;
  blurVariance: number;
  meanBrightness: number;
  glarePercentage: number;
  aspectRatio?: number;
  occlusionRatio?: number;
}

export interface QualityAssessment {
  passed: boolean;
  score: number; // 0 - 100
  statusText: string;
  issues: QualityIssue[];
  metrics: QualityMetrics;
}

/**
 * Thresholds tuned for mobile smartphone packaging photos
 */
export const QUALITY_THRESHOLDS = {
  MIN_WIDTH: 600,
  MIN_HEIGHT: 600,
  BLUR_THRESHOLD: 120, // Laplacian variance < 120 indicates blur
  MIN_BRIGHTNESS: 42, // Mean grayscale < 42 is too dark
  MAX_GLARE_RATIO: 0.08, // Over 8% saturated white pixels in center region = glare
  MAX_ASPECT_RATIO: 3.0, // Aspect ratio > 3:1 or < 1:3 indicates extreme perspective or narrow crop
  MAX_OCCLUSION_RATIO: 0.40, // Over 40% uniform tone in center indicates finger/shadow obstruction
};

/**
 * Analyzes an image (from a data URL or Image element) on an offscreen canvas
 */
export async function assessImageQuality(dataUrl: string): Promise<QualityAssessment> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";

    img.onload = () => {
      const width = img.naturalWidth || img.width;
      const height = img.naturalHeight || img.height;

      // Sample down to max 640px width for fast, reliable client-side processing
      const scale = Math.min(1, 640 / Math.max(width, height));
      const sampleWidth = Math.round(width * scale);
      const sampleHeight = Math.round(height * scale);

      const canvas = document.createElement("canvas");
      canvas.width = sampleWidth;
      canvas.height = sampleHeight;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });

      if (!ctx) {
        // Fallback if 2D context fails
        resolve({
          passed: true,
          score: 80,
          statusText: "QUALITY CHECK BYPASSED",
          issues: [],
          metrics: {
            width,
            height,
            blurVariance: 200,
            meanBrightness: 128,
            glarePercentage: 0,
          },
        });
        return;
      }

      ctx.drawImage(img, 0, 0, sampleWidth, sampleHeight);
      const imageData = ctx.getImageData(0, 0, sampleWidth, sampleHeight);
      const data = imageData.data;

      // 1. Grayscale & Luminance Analysis
      const totalPixels = sampleWidth * sampleHeight;
      const gray = new Float32Array(totalPixels);
      let brightnessSum = 0;
      let glarePixelsInCenter = 0;

      const centerLeft = Math.floor(sampleWidth * 0.15);
      const centerRight = Math.floor(sampleWidth * 0.85);
      const centerTop = Math.floor(sampleHeight * 0.15);
      const centerBottom = Math.floor(sampleHeight * 0.85);
      const centerPixels = (centerRight - centerLeft) * (centerBottom - centerTop);
      const centerBins = new Uint32Array(16);

      for (let i = 0; i < totalPixels; i++) {
        const r = data[i * 4];
        const g = data[i * 4 + 1];
        const b = data[i * 4 + 2];
        // Standard Rec. 601 luminance
        const lum = 0.299 * r + 0.587 * g + 0.114 * b;
        gray[i] = lum;
        brightnessSum += lum;

        // Check glare and occlusion in center zone
        const x = i % sampleWidth;
        const y = Math.floor(i / sampleWidth);
        if (x >= centerLeft && x <= centerRight && y >= centerTop && y <= centerBottom) {
          const bin = Math.min(15, Math.floor(lum / 16));
          centerBins[bin]++;
          if (r > 245 && g > 245 && b > 245) {
            glarePixelsInCenter++;
          }
        }
      }

      const meanBrightness = brightnessSum / totalPixels;
      const glarePercentage = glarePixelsInCenter / centerPixels;
      let maxCenterBin = 0;
      for (let b = 0; b < 16; b++) {
        if (centerBins[b] > maxCenterBin) maxCenterBin = centerBins[b];
      }
      const occlusionRatio = centerPixels > 0 ? maxCenterBin / centerPixels : 0;

      // 2. Blur Estimation via 3x3 Laplacian operator
      // Kernel:
      //  0  1  0
      //  1 -4  1
      //  0  1  0
      let laplacianSum = 0;
      let laplacianSqSum = 0;
      let laplacianCount = 0;

      for (let y = 1; y < sampleHeight - 1; y++) {
        const row = y * sampleWidth;
        const rowAbove = (y - 1) * sampleWidth;
        const rowBelow = (y + 1) * sampleWidth;

        for (let x = 1; x < sampleWidth - 1; x++) {
          const val =
            gray[rowAbove + x] +
            gray[rowBelow + x] +
            gray[row + x - 1] +
            gray[row + x + 1] -
            4 * gray[row + x];

          laplacianSum += val;
          laplacianSqSum += val * val;
          laplacianCount++;
        }
      }

      const laplacianMean = laplacianSum / laplacianCount;
      const blurVariance = laplacianSqSum / laplacianCount - laplacianMean * laplacianMean;

      // 3. Issue Evaluation & Specific Retake Guidance
      const issues: QualityIssue[] = [];

      // Blur check (CAP-03)
      if (blurVariance < QUALITY_THRESHOLDS.BLUR_THRESHOLD) {
        issues.push({
          type: "blur",
          severity: "error",
          title: "Blur Detected",
          message: "Text edges are soft or out of focus.",
          actionHint: "Hold camera steady, tap to refocus on label text, then retake.",
        });
      }

      // Lighting & Glare check (CAP-04)
      if (meanBrightness < QUALITY_THRESHOLDS.MIN_BRIGHTNESS) {
        issues.push({
          type: "too_dark",
          severity: "error",
          title: "Lighting Too Dark",
          message: "Insufficient lighting makes declaration text illegible.",
          actionHint: "Turn on the flash toggle or move to a brighter area.",
        });
      }

      if (glarePercentage > QUALITY_THRESHOLDS.MAX_GLARE_RATIO) {
        issues.push({
          type: "glare",
          severity: "warning",
          title: "Reflection / Glare Detected",
          message: "Bright glare reflection covers part of the label surface.",
          actionHint: "Tilt device slightly (15°–20°) to shift reflection off the text.",
        });
      }

      // Resolution check (CAP-05)
      if (width < QUALITY_THRESHOLDS.MIN_WIDTH || height < QUALITY_THRESHOLDS.MIN_HEIGHT) {
        issues.push({
          type: "low_resolution",
          severity: "error",
          title: "Low Resolution",
          message: `Image resolution (${width}×${height}) is below 600px minimum.`,
          actionHint: "Move closer to the package so the label occupies most of the frame.",
        });
      }

      // Perspective & Aspect Ratio check (CAP-05)
      const aspectRatio = width / Math.max(1, height);
      const isExtremeAspect =
        aspectRatio > QUALITY_THRESHOLDS.MAX_ASPECT_RATIO ||
        aspectRatio < (1 / QUALITY_THRESHOLDS.MAX_ASPECT_RATIO);
      if (isExtremeAspect) {
        issues.push({
          type: "perspective",
          severity: "warning",
          title: "Extreme Perspective / Aspect Skew",
          message: `Package aspect ratio (${aspectRatio.toFixed(2)}) is unusually steep or narrow.`,
          actionHint: "Position the camera directly parallel/flat to the principal display panel.",
        });
      }

      // Occlusion check (CAP-05)
      const isOccluded =
        occlusionRatio > QUALITY_THRESHOLDS.MAX_OCCLUSION_RATIO &&
        blurVariance >= QUALITY_THRESHOLDS.BLUR_THRESHOLD;
      if (isOccluded) {
        issues.push({
          type: "perspective",
          severity: "warning",
          title: "Label Occlusion Detected",
          message: "A large uniform obstruction or heavy shadow covers over 40% of the center label area.",
          actionHint: "Ensure fingers, thumbs, and shadows are clear of mandatory declarations before shooting.",
        });
      }

      // 4. Compute Overall Score
      const hasErrors = issues.some((i) => i.severity === "error");
      const passed = !hasErrors;
      let score = 100;
      if (blurVariance < QUALITY_THRESHOLDS.BLUR_THRESHOLD) score -= 40;
      if (meanBrightness < QUALITY_THRESHOLDS.MIN_BRIGHTNESS) score -= 30;
      if (glarePercentage > QUALITY_THRESHOLDS.MAX_GLARE_RATIO) score -= 20;
      if (width < QUALITY_THRESHOLDS.MIN_WIDTH) score -= 25;
      if (isExtremeAspect) score -= 15;
      if (isOccluded) score -= 15;
      score = Math.max(10, Math.min(100, score));

      let statusText = "QUALITY CHECK PASSED";
      if (!passed) {
        statusText = issues[0]?.title.toUpperCase() || "QUALITY CHECK FAILED";
      } else if (issues.length > 0) {
        statusText = "ACCEPTABLE (WITH WARNINGS)";
      }

      resolve({
        passed,
        score,
        statusText,
        issues,
        metrics: {
          width,
          height,
          blurVariance: Math.round(blurVariance),
          meanBrightness: Math.round(meanBrightness),
          glarePercentage: Math.round(glarePercentage * 100) / 100,
          aspectRatio: Math.round(aspectRatio * 100) / 100,
          occlusionRatio: Math.round(occlusionRatio * 100) / 100,
        },
      });
    };

    img.onerror = () => {
      resolve({
        passed: false,
        score: 0,
        statusText: "IMAGE READ ERROR",
        issues: [
          {
            type: "low_resolution",
            severity: "error",
            title: "Corrupt Image",
            message: "Unable to parse captured image frame.",
            actionHint: "Please retake the photo.",
          },
        ],
        metrics: {
          width: 0,
          height: 0,
          blurVariance: 0,
          meanBrightness: 0,
          glarePercentage: 0,
          aspectRatio: 1,
          occlusionRatio: 0,
        },
      });
    };

    img.src = dataUrl;
  });
}
