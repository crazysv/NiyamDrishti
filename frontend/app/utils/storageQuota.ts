import { getPendingSyncCount } from "../db/dexie";

export const MAX_OFFLINE_QUEUE_DEPTH = 50;
export const WARN_OFFLINE_QUEUE_DEPTH = 40;
export const MIN_AVAILABLE_STORAGE_MB = 50;
export const CRITICAL_STORAGE_USAGE_PERCENT = 90;

export interface StorageEstimateResult {
  usedBytes: number;
  quotaBytes: number;
  availableMB: number;
  usagePercent: number;
  isSupported: boolean;
}

export interface StorageHealthStatus {
  isLowSpace: boolean;
  isQueueFull: boolean;
  isWarning: boolean;
  severity: "normal" | "warning" | "critical";
  queueCount: number;
  maxQueueCount: number;
  availableMB: number;
  usagePercent: number;
  title: string;
  message: string;
}

/**
 * Queries the browser StorageManager API for storage estimate (STOR-03).
 */
export async function getStorageEstimate(): Promise<StorageEstimateResult> {
  if (typeof window !== "undefined" && navigator.storage && navigator.storage.estimate) {
    try {
      const estimate = await navigator.storage.estimate();
      const usedBytes = estimate.usage || 0;
      const quotaBytes = estimate.quota || 0;
      const availableBytes = Math.max(0, quotaBytes - usedBytes);
      const availableMB = Math.round(availableBytes / (1024 * 1024));
      const usagePercent = quotaBytes > 0 ? Math.round((usedBytes / quotaBytes) * 100) : 0;

      return {
        usedBytes,
        quotaBytes,
        availableMB,
        usagePercent,
        isSupported: true,
      };
    } catch {
      // Fallback if permission error or browser restriction
    }
  }

  // Graceful fallback for unsupported environments
  return {
    usedBytes: 0,
    quotaBytes: 0,
    availableMB: 500,
    usagePercent: 0,
    isSupported: false,
  };
}

/**
 * Assesses both device quota and offline queue depth against regulatory caps (STOR-03).
 */
export async function checkStorageHealth(): Promise<StorageHealthStatus> {
  const estimate = await getStorageEstimate();
  let queueCount = 0;
  try {
    queueCount = await getPendingSyncCount();
  } catch {
    queueCount = 0;
  }

  const isQueueFull = queueCount >= MAX_OFFLINE_QUEUE_DEPTH;
  const isQueueNearCap = queueCount >= WARN_OFFLINE_QUEUE_DEPTH;
  const isDeviceLowSpace =
    estimate.isSupported &&
    (estimate.availableMB < MIN_AVAILABLE_STORAGE_MB ||
      estimate.usagePercent >= CRITICAL_STORAGE_USAGE_PERCENT);

  if (isQueueFull) {
    return {
      isLowSpace: true,
      isQueueFull: true,
      isWarning: true,
      severity: "critical",
      queueCount,
      maxQueueCount: MAX_OFFLINE_QUEUE_DEPTH,
      availableMB: estimate.availableMB,
      usagePercent: estimate.usagePercent,
      title: "Offline Storage Queue Cap Reached",
      message: `Offline queue has reached the maximum capacity of ${MAX_OFFLINE_QUEUE_DEPTH} packages. Please connect to the internet and synchronize pending inspections before capturing more products.`,
    };
  }

  if (isDeviceLowSpace) {
    return {
      isLowSpace: true,
      isQueueFull: false,
      isWarning: true,
      severity: "critical",
      queueCount,
      maxQueueCount: MAX_OFFLINE_QUEUE_DEPTH,
      availableMB: estimate.availableMB,
      usagePercent: estimate.usagePercent,
      title: "Device Storage Running Critically Low",
      message: `Available browser storage is under ${MIN_AVAILABLE_STORAGE_MB}MB (${estimate.availableMB}MB free). Risk of image eviction. Please synchronize immediately.`,
    };
  }

  if (isQueueNearCap) {
    return {
      isLowSpace: false,
      isQueueFull: false,
      isWarning: true,
      severity: "warning",
      queueCount,
      maxQueueCount: MAX_OFFLINE_QUEUE_DEPTH,
      availableMB: estimate.availableMB,
      usagePercent: estimate.usagePercent,
      title: "Offline Storage Queue Near Capacity",
      message: `${queueCount} of ${MAX_OFFLINE_QUEUE_DEPTH} offline packages queued. Consider synchronizing when network is available.`,
    };
  }

  return {
    isLowSpace: false,
    isQueueFull: false,
    isWarning: false,
    severity: "normal",
    queueCount,
    maxQueueCount: MAX_OFFLINE_QUEUE_DEPTH,
    availableMB: estimate.availableMB,
    usagePercent: estimate.usagePercent,
    title: "Storage Healthy",
    message: "Adequate device storage available for offline inspections.",
  };
}
