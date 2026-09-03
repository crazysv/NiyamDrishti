import {
  db,
  getPendingInspections,
  updateInspectionSyncState,
  updateImageSyncState,
  markInspectionDeadLetter,
  resolveInspectionConflict,
  resetFailedInspectionForRetry,
  discardOfflineInspection,
  OfflineImage,
} from '@/app/db/dexie';
import {
  fetchWithRetry,
  SyncConflictError,
  SyncPermanentError,
  SyncTransientError,
  calculateBackoffWithJitter,
} from '@/app/utils/retryBackoff';

import { API_BASE } from '@/app/utils/apiConfig';
const MAX_AUTO_RETRIES = 5;

function getAuthHeaders(token?: string, idempotencyKey?: string): Record<string, string> {
  const resolvedToken =
    token ||
    (typeof window !== 'undefined'
      ? localStorage.getItem('access_token') || localStorage.getItem('token')
      : null);

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (resolvedToken) {
    headers['Authorization'] = 'Bearer ' + resolvedToken;
  }

  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }

  return headers;
}

/**
 * Resumably syncs a single offline inspection and its images to the backend (E4-02).
 * Supports exponential retry with full jitter, idempotency keys, and deterministic conflict resolution.
 */
export async function syncSingleInspection(
  inspectionId: string,
  token?: string
): Promise<{ success: boolean; error?: string; conflicted?: boolean }> {
  const inspection = await db.inspections.get(inspectionId);
  if (!inspection) {
    return { success: false, error: 'Inspection not found in offline storage' };
  }

  if (inspection.status === 'synced') {
    return { success: true };
  }

  const currentRetries = (inspection.retryCount || 0) + 1;
  const nowIso = new Date().toISOString();

  await updateInspectionSyncState(inspectionId, {
    status: 'syncing',
    retryCount: currentRetries,
    lastAttemptAt: nowIso,
    syncError: undefined,
  });

  let backendInspectionId = inspection.backendId;

  // Step 1: Create remote inspection if not already created (or fetch existing idempotently)
  if (!backendInspectionId) {
    try {
      const resp = await fetchWithRetry(
        API_BASE + '/inspections',
        {
          method: 'POST',
          headers: getAuthHeaders(token, inspection.id),
          body: JSON.stringify({
            client_id: inspection.id,
            commodity_category: inspection.commodityCategory,
            captured_offline: true,
            is_self_check: false,
            created_at: inspection.createdAt,
          }),
        },
        {
          maxRetries: 2,
          onRetry: (attempt, delay, reason) => {
            console.warn('[Sync] Retrying inspection create (' + attempt + '): ' + reason);
          },
        }
      );

      const created = await resp.json();
      backendInspectionId = created.id;
      await updateInspectionSyncState(inspectionId, { backendId: backendInspectionId });
    } catch (err: unknown) {
      // Conflict resolution: Inspection was already completed on the server
      if (err instanceof SyncConflictError) {
        if (err.suggestedResolution === 'server_authoritative' || err.code === 'INSPECTION_FINALIZED') {
          await resolveInspectionConflict(inspectionId, 'server_authoritative');
          return { success: true, conflicted: true };
        } else {
          await markInspectionDeadLetter(inspectionId, 'conflict', err.message, {
            code: err.code,
            message: err.message,
            serverStatus: err.serverStatus,
            suggestedResolution: err.suggestedResolution,
          });
          return { success: false, error: err.message, conflicted: true };
        }
      }

      // Permanent error (e.g. invalid payload or forbidden)
      if (err instanceof SyncPermanentError) {
        const msg = 'Permanent error: ' + err.message;
        await markInspectionDeadLetter(inspectionId, 'permanent', msg);
        return { success: false, error: msg };
      }

      // Transient network failure
      const errMsg = err instanceof Error ? err.message : 'Network error creating inspection';
      if (currentRetries >= MAX_AUTO_RETRIES) {
        await markInspectionDeadLetter(
          inspectionId,
          'transient',
          'Maximum retry attempts (' + MAX_AUTO_RETRIES + ') exceeded: ' + errMsg
        );
      } else {
        const backoffDelay = calculateBackoffWithJitter(currentRetries, 1000, 30000);
        const nextRetry = new Date(Date.now() + backoffDelay).toISOString();
        await updateInspectionSyncState(inspectionId, {
          status: 'failed',
          failureCategory: 'transient',
          nextRetryAt: nextRetry,
          syncError: errMsg,
        });
      }
      return { success: false, error: errMsg };
    }
  }

  // Step 2: Upload unsynced images one by one (resumable and idempotent per-item)
  const images: OfflineImage[] = await db.inspectionImages
    .where('inspectionId')
    .equals(inspectionId)
    .toArray();

  let allImagesSucceeded = true;

  for (const img of images) {
    if (img.isSynced) {
      continue;
    }

    try {
      const imgResp = await fetchWithRetry(
        `${API_BASE}/inspections/${backendInspectionId}/images`,
        {
          method: 'POST',
          headers: getAuthHeaders(token, img.id),
          body: JSON.stringify({
            client_id: img.id,
            image_role: img.imageRole,
            data_url: img.dataUrl,
            quality_check_passed: img.qualityAssessment?.passed ?? true,
            captured_at: img.createdAt,
          }),
        },
        {
          maxRetries: 2,
          onRetry: (attempt, delay, reason) => {
            console.warn('[Sync] Retrying image ' + img.imageRole + ' (' + attempt + '): ' + reason);
          },
        }
      );

      const createdImg = await imgResp.json();
      await updateImageSyncState(img.id, {
        isSynced: true,
        backendImageId: createdImg.id,
        syncError: undefined,
      });
    } catch (err: unknown) {
      // If server inspection is already finalized during image upload, treat server as authoritative
      if (err instanceof SyncConflictError && err.code === 'INSPECTION_FINALIZED') {
        await updateImageSyncState(img.id, { isSynced: true });
        continue;
      }

      const errorMsg = err instanceof Error ? err.message : 'Error uploading image';
      await updateImageSyncState(img.id, { syncError: errorMsg });
      allImagesSucceeded = false;
    }
  }

  // Step 3: Finalize status
  if (allImagesSucceeded) {
    await updateInspectionSyncState(inspectionId, {
      status: 'synced',
      syncedAt: new Date().toISOString(),
      syncError: undefined,
      failureCategory: undefined,
    });
    return { success: true };
  } else {
    if (currentRetries >= MAX_AUTO_RETRIES) {
      await markInspectionDeadLetter(
        inspectionId,
        'transient',
        'One or more images failed after ' + MAX_AUTO_RETRIES + ' attempts.'
      );
    } else {
      const backoffDelay = calculateBackoffWithJitter(currentRetries, 1000, 30000);
      const nextRetry = new Date(Date.now() + backoffDelay).toISOString();
      await updateInspectionSyncState(inspectionId, {
        status: 'failed',
        failureCategory: 'transient',
        nextRetryAt: nextRetry,
        syncError: 'One or more images failed to upload. Retrying automatically.',
      });
    }
    return { success: false, error: 'Some images failed to upload' };
  }
}

/**
 * Consolidated Batch Offline Sync (E4-02):
 * Sends all queued inspections to the atomic /sync endpoint when possible.
 */
export async function syncAllQueuedInspections(
  token?: string,
  onProgress?: (synced: number, total: number) => void
): Promise<{ total: number; successful: number; failed: number; conflicted: number }> {
  const pendingItems = await getPendingInspections();
  const total = pendingItems.length;

  if (total === 0) {
    return { total: 0, successful: 0, failed: 0, conflicted: 0 };
  }

  let successful = 0;
  let failed = 0;
  let conflicted = 0;

  for (let i = 0; i < pendingItems.length; i++) {
    const item = pendingItems[i];
    const res = await syncSingleInspection(item.inspection.id, token);
    if (res.success) {
      successful++;
      if (res.conflicted) conflicted++;
    } else {
      failed++;
    }
    if (onProgress) {
      onProgress(i + 1, total);
    }
  }

  return { total, successful, failed, conflicted };
}

/**
 * Retries all failed and dead-letter inspections by resetting their retry counter and re-queueing
 */
export async function retryAllFailedInspections(token?: string): Promise<{ total: number; retried: number }> {
  const failedItems = await db.inspections
    .where('status')
    .anyOf(['failed', 'dead_letter'])
    .toArray();

  for (const item of failedItems) {
    await resetFailedInspectionForRetry(item.id);
  }

  const result = await syncAllQueuedInspections(token);
  return { total: failedItems.length, retried: result.successful };
}
