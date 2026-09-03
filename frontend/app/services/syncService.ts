import {
  db,
  getPendingInspections,
  updateInspectionSyncState,
  updateImageSyncState,
  OfflineImage,
} from "@/app/db/dexie";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthHeaders(token?: string): Record<string, string> {
  const resolvedToken =
    token ||
    (typeof window !== "undefined"
      ? localStorage.getItem("access_token") || localStorage.getItem("token")
      : null);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (resolvedToken) {
    headers["Authorization"] = `Bearer ${resolvedToken}`;
  }

  return headers;
}

/**
 * Resumably syncs a single offline inspection and its images to the backend.
 */
export async function syncSingleInspection(
  inspectionId: string,
  token?: string
): Promise<{ success: boolean; error?: string }> {
  const inspection = await db.inspections.get(inspectionId);
  if (!inspection) {
    return { success: false, error: "Inspection not found in offline storage" };
  }

  if (inspection.status === "synced") {
    return { success: true };
  }

  await updateInspectionSyncState(inspectionId, { status: "syncing", syncError: undefined });

  let backendInspectionId = inspection.backendId;

  // Step 1: Create remote inspection if not already created
  if (!backendInspectionId) {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/inspections`, {
        method: "POST",
        headers: getAuthHeaders(token),
        body: JSON.stringify({
          commodity_category: inspection.commodityCategory,
          captured_offline: true,
          is_self_check: false,
          created_at: inspection.createdAt,
        }),
      });

      if (!resp.ok) {
        const errorText = await resp.text();
        const msg = `Failed to create inspection: HTTP ${resp.status} - ${errorText}`;
        await updateInspectionSyncState(inspectionId, { status: "failed", syncError: msg });
        return { success: false, error: msg };
      }

      const created = await resp.json();
      backendInspectionId = created.id;
      await updateInspectionSyncState(inspectionId, { backendId: backendInspectionId });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network error creating inspection";
      await updateInspectionSyncState(inspectionId, { status: "failed", syncError: msg });
      return { success: false, error: msg };
    }
  }

  // Step 2: Upload unsynced images one by one (resumable per-item)
  const images: OfflineImage[] = await db.inspectionImages
    .where("inspectionId")
    .equals(inspectionId)
    .toArray();

  let allImagesSucceeded = true;

  for (const img of images) {
    if (img.isSynced) {
      continue;
    }

    try {
      const imgResp = await fetch(
        `${API_BASE_URL}/api/v1/inspections/${backendInspectionId}/images`,
        {
          method: "POST",
          headers: getAuthHeaders(token),
          body: JSON.stringify({
            image_role: img.imageRole,
            data_url: img.dataUrl,
            quality_check_passed: img.qualityAssessment?.passed ?? true,
            captured_at: img.createdAt,
          }),
        }
      );

      if (!imgResp.ok) {
        const errorText = await imgResp.text();
        const errorMsg = `Image ${img.imageRole} upload failed: HTTP ${imgResp.status} - ${errorText}`;
        await updateImageSyncState(img.id, { syncError: errorMsg });
        allImagesSucceeded = false;
        continue;
      }

      const createdImg = await imgResp.json();
      await updateImageSyncState(img.id, {
        isSynced: true,
        backendImageId: createdImg.id,
        syncError: undefined,
      });
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Network error uploading image";
      await updateImageSyncState(img.id, { syncError: errorMsg });
      allImagesSucceeded = false;
    }
  }

  // Step 3: Finalize status
  if (allImagesSucceeded) {
    await updateInspectionSyncState(inspectionId, {
      status: "synced",
      syncedAt: new Date().toISOString(),
      syncError: undefined,
    });
    return { success: true };
  } else {
    await updateInspectionSyncState(inspectionId, {
      status: "failed",
      syncError: "One or more images failed to upload. Retry when connection improves.",
    });
    return { success: false, error: "Some images failed to upload" };
  }
}

/**
 * Resumes and syncs all queued or failed inspections upon reconnect.
 */
export async function syncAllQueuedInspections(
  token?: string,
  onProgress?: (synced: number, total: number) => void
): Promise<{ total: number; successful: number; failed: number }> {
  const pendingItems = await getPendingInspections();
  const total = pendingItems.length;

  if (total === 0) {
    return { total: 0, successful: 0, failed: 0 };
  }

  let successful = 0;
  let failed = 0;

  for (let i = 0; i < pendingItems.length; i++) {
    const item = pendingItems[i];
    const res = await syncSingleInspection(item.inspection.id, token);
    if (res.success) {
      successful++;
    } else {
      failed++;
    }
    if (onProgress) {
      onProgress(i + 1, total);
    }
  }

  return { total, successful, failed };
}
