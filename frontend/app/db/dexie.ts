import Dexie, { type EntityTable } from "dexie";
import { ImageRole, CommodityCategory } from "@/app/types/capture";
import { QualityAssessment } from "@/app/utils/qualityGate";

export type SyncStatus = "draft" | "sync_pending" | "syncing" | "synced" | "failed" | "dead_letter";

export interface OfflineConflictDetails {
  code: string;
  message: string;
  serverStatus?: string;
  suggestedResolution?: string;
  resolvedAt?: string;
  resolutionStrategy?: string;
}

export interface OfflineInspection {
  id: string;
  backendId?: string;
  status: SyncStatus;
  commodityCategory: CommodityCategory;
  rulePackVersion: string;
  capturedOffline: boolean;
  createdAt: string;
  updatedAt: string;
  syncedAt?: string;
  syncError?: string;
  retryCount?: number;
  lastAttemptAt?: string;
  nextRetryAt?: string;
  failureCategory?: "transient" | "conflict" | "permanent";
  conflictDetails?: OfflineConflictDetails;
}

export interface OfflineImage {
  id: string;
  inspectionId: string;
  imageRole: ImageRole;
  dataUrl: string;
  qualityAssessment?: QualityAssessment;
  isSynced?: boolean;
  backendImageId?: string;
  syncError?: string;
  createdAt: string;
  clientId?: string;
  retryCount?: number;
}

// Dexie Database schema
class NiyamDrishtiDatabase extends Dexie {
  inspections!: EntityTable<OfflineInspection, "id">;
  inspectionImages!: EntityTable<OfflineImage, "id">;

  constructor() {
    super("NiyamDrishtiOfflineDB");
    this.version(1).stores({
      inspections: "id, status, commodityCategory, createdAt, capturedOffline",
      inspectionImages: "id, inspectionId, imageRole, createdAt",
    });
    this.version(2).stores({
      inspections: "id, backendId, status, commodityCategory, createdAt, capturedOffline",
      inspectionImages: "id, inspectionId, imageRole, isSynced, createdAt",
    });
    this.version(3).stores({
      inspections: "id, backendId, status, commodityCategory, createdAt, capturedOffline, failureCategory",
      inspectionImages: "id, inspectionId, imageRole, isSynced, createdAt, clientId",
    });
  }
}

export const db = new NiyamDrishtiDatabase();

/**
 * Saves a completed inspection package to IndexedDB with 'sync_pending' status
 */
export async function queueInspectionForSync(
  inspectionId: string,
  category: CommodityCategory,
  images: { role: ImageRole; dataUrl: string; qualityAssessment?: QualityAssessment }[],
  isOffline: boolean
): Promise<OfflineInspection> {
  const now = new Date().toISOString();

  const inspection: OfflineInspection = {
    id: inspectionId,
    status: "sync_pending",
    commodityCategory: category,
    rulePackVersion: "2026.02.01",
    capturedOffline: isOffline,
    createdAt: now,
    updatedAt: now,
  };

  const offlineImages: OfflineImage[] = images.map((img) => ({
    id: `img_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    inspectionId,
    imageRole: img.role,
    dataUrl: img.dataUrl,
    qualityAssessment: img.qualityAssessment,
    isSynced: false,
    createdAt: now,
  }));

  await db.transaction("rw", db.inspections, db.inspectionImages, async () => {
    await db.inspections.put(inspection);
    for (const img of offlineImages) {
      await db.inspectionImages.put(img);
    }
  });

  return inspection;
}

/**
 * Returns count of items pending sync (including failed items)
 */
export async function getPendingSyncCount(): Promise<number> {
  return await db.inspections
    .where("status")
    .anyOf(["sync_pending", "failed"])
    .count();
}

/**
 * Retrieves all inspections currently queued or failed for sync
 */
export async function getPendingInspections(): Promise<
  { inspection: OfflineInspection; images: OfflineImage[] }[]
> {
  const pending = await db.inspections
    .where("status")
    .anyOf(["sync_pending", "failed"])
    .toArray();
  const results = [];

  for (const item of pending) {
    const images = await db.inspectionImages.where("inspectionId").equals(item.id).toArray();
    results.push({ inspection: item, images });
  }

  return results;
}

/**
 * Updates an inspection's status and optional backend ID
 */
export async function updateInspectionSyncState(
  inspectionId: string,
  updates: Partial<OfflineInspection>
): Promise<void> {
  await db.inspections.update(inspectionId, {
    ...updates,
    updatedAt: new Date().toISOString(),
  });
}

/**
 * Updates an image's sync state
 */
export async function updateImageSyncState(
  imageId: string,
  updates: Partial<OfflineImage>
): Promise<void> {
  await db.inspectionImages.update(imageId, updates);
}

/**
 * Checks storage quota estimate
 */
export async function getStorageQuota(): Promise<{
  usageMb: number;
  quotaMb: number;
  percentUsed: number;
  isLowSpace: boolean;
}> {
  if (typeof navigator !== "undefined" && navigator.storage && navigator.storage.estimate) {
    const estimate = await navigator.storage.estimate();
    const usageMb = Math.round((estimate.usage || 0) / (1024 * 1024));
    const quotaMb = Math.round((estimate.quota || 0) / (1024 * 1024));
    const percentUsed = quotaMb > 0 ? Math.round((usageMb / quotaMb) * 100) : 0;
    const isLowSpace = percentUsed > 85;
    return { usageMb, quotaMb, percentUsed, isLowSpace };
  }
  return { usageMb: 0, quotaMb: 0, percentUsed: 0, isLowSpace: false };
}

/**
 * Returns count of items currently in dead_letter state (requiring officer review/conflict resolution)
 */
export async function getDeadLetterCount(): Promise<number> {
  return await db.inspections.where("status").equals("dead_letter").count();
}

/**
 * Returns count of items in transient failed state
 */
export async function getFailedSyncCount(): Promise<number> {
  return await db.inspections.where("status").equals("failed").count();
}

/**
 * Retrieves all inspections currently in dead_letter state
 */
export async function getDeadLetterInspections(): Promise<
  { inspection: OfflineInspection; images: OfflineImage[] }[]
> {
  const deadLetters = await db.inspections.where("status").equals("dead_letter").toArray();
  const results = [];

  for (const item of deadLetters) {
    const images = await db.inspectionImages.where("inspectionId").equals(item.id).toArray();
    results.push({ inspection: item, images });
  }

  return results;
}

/**
 * Marks an inspection as dead_letter with categorized failure details
 */
export async function markInspectionDeadLetter(
  inspectionId: string,
  failureCategory: "transient" | "conflict" | "permanent",
  errorMsg: string,
  conflictDetails?: OfflineConflictDetails
): Promise<void> {
  await db.inspections.update(inspectionId, {
    status: "dead_letter",
    failureCategory,
    syncError: errorMsg,
    conflictDetails,
    updatedAt: new Date().toISOString(),
  });
}

/**
 * Resets a failed or dead-letter inspection back to sync_pending with retryCount=0
 */
export async function resetFailedInspectionForRetry(inspectionId: string): Promise<void> {
  await db.inspections.update(inspectionId, {
    status: "sync_pending",
    retryCount: 0,
    syncError: undefined,
    failureCategory: undefined,
    updatedAt: new Date().toISOString(),
  });
}

/**
 * Resolves a conflict on an offline inspection:
 * - 'server_authoritative': marks local inspection as synced with resolved conflict metadata
 * - 'discard': deletes the local inspection draft
 */
export async function resolveInspectionConflict(
  inspectionId: string,
  strategy: "server_authoritative" | "discard"
): Promise<void> {
  if (strategy === "discard") {
    await discardOfflineInspection(inspectionId);
    return;
  }

  const existing = await db.inspections.get(inspectionId);
  const updatedDetails: OfflineConflictDetails | undefined = existing?.conflictDetails
    ? {
        ...existing.conflictDetails,
        resolvedAt: new Date().toISOString(),
        resolutionStrategy: "server_authoritative",
      }
    : undefined;

  await db.inspections.update(inspectionId, {
    status: "synced",
    syncedAt: new Date().toISOString(),
    syncError: undefined,
    failureCategory: undefined,
    conflictDetails: updatedDetails,
    updatedAt: new Date().toISOString(),
  });
}

/**
 * Permanently discards an offline inspection and its attached images from IndexedDB
 */
export async function discardOfflineInspection(inspectionId: string): Promise<void> {
  await db.transaction("rw", db.inspections, db.inspectionImages, async () => {
    await db.inspectionImages.where("inspectionId").equals(inspectionId).delete();
    await db.inspections.delete(inspectionId);
  });
}

