import Dexie, { type EntityTable } from "dexie";
import { ImageRole, CommodityCategory } from "@/app/types/capture";
import { QualityAssessment } from "@/app/utils/qualityGate";

export type SyncStatus = "draft" | "sync_pending" | "syncing" | "synced" | "failed";

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
