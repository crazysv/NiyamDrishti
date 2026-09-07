import {
  db,
  getPendingInspections,
  updateInspectionSyncState,
  updateImageSyncState,
  markInspectionDeadLetter,
  resolveInspectionConflict,
  resetFailedInspectionForRetry,
  OfflineImage,
} from '@/app/db/dexie';
import {
  fetchWithRetry,
  SyncConflictError,
  SyncPermanentError,
  calculateBackoffWithJitter,
} from '@/app/utils/retryBackoff';

import { API_BASE } from '@/app/utils/apiConfig';
const MAX_AUTO_RETRIES = 5;
const MAX_UPLOAD_BYTES = 420 * 1024;

function dataUrlToBlob(dataUrl: string): Blob {
  const [header, encoded] = dataUrl.split(',', 2);
  if (!header || !encoded) {
    throw new Error('Stored photo is not a valid data URL');
  }
  const mimeType = header.match(/^data:([^;]+);base64$/)?.[1] || 'image/jpeg';
  const bytes = atob(encoded);
  const buffer = new Uint8Array(bytes.length);
  for (let index = 0; index < bytes.length; index += 1) {
    buffer[index] = bytes.charCodeAt(index);
  }
  return new Blob([buffer], { type: mimeType });
}

/** Re-encode legacy queued photos too, so retrying an old inspection is safe. */
async function prepareImageBlobForUpload(dataUrl: string): Promise<Blob> {
  const original = dataUrlToBlob(dataUrl);
  if (original.size <= MAX_UPLOAD_BYTES || typeof document === 'undefined') {
    return original;
  }

  const image = new Image();
  image.src = dataUrl;
  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error('Stored photo could not be prepared for upload'));
  });

  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (!context) return original;

  let maxEdge = 1280;
  let quality = 0.78;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const scale = Math.min(1, maxEdge / Math.max(image.naturalWidth, image.naturalHeight));
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const encoded = canvas.toDataURL('image/jpeg', quality);
    const compacted = dataUrlToBlob(encoded);
    if (compacted.size <= MAX_UPLOAD_BYTES || maxEdge <= 640) return compacted;
    maxEdge = Math.max(640, Math.round(maxEdge * 0.78));
    quality = Math.max(0.62, quality - 0.05);
  }

  return original;
}

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

async function ensureAuthToken(explicitToken?: string, forceRefresh?: boolean): Promise<string | null> {
  if (explicitToken && !forceRefresh) return explicitToken;
  if (typeof window === 'undefined') return null;

  if (!forceRefresh) {
    const existing = localStorage.getItem('access_token') || localStorage.getItem('token');
    if (existing) return existing;
  }

  try {
    const { authorizeSandboxPersona, handleSSOCallback } = await import('@/app/services/ssoService');
    const nonce = 'sync_auto_' + Date.now();
    const authRes = await authorizeSandboxPersona('officer_suresh', nonce);
    const tokenRes = await handleSSOCallback(authRes.code, authRes.state);
    return tokenRes.access_token;
  } catch (err) {
    console.warn('[Sync] Auto-login fallback could not acquire token:', err);
    return null;
  }
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

  let currentToken = (await ensureAuthToken(token)) || undefined;
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
          headers: getAuthHeaders(currentToken, inspection.id),
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
      // Automatic 401 recovery: Invalidate stale token and retry with fresh sandbox token
      if (err instanceof SyncPermanentError && (err.statusCode === 401 || err.message.includes('401'))) {
        console.warn('[Sync] 401 Unauthorized received. Re-authenticating via sandbox SSO...');
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          localStorage.removeItem('token');
        }
        const freshToken = await ensureAuthToken(undefined, true);
        if (freshToken) {
          currentToken = freshToken;
          try {
            const retryResp = await fetch(API_BASE + '/inspections', {
              method: 'POST',
              headers: getAuthHeaders(freshToken, inspection.id),
              body: JSON.stringify({
                client_id: inspection.id,
                commodity_category: inspection.commodityCategory,
                captured_offline: true,
                is_self_check: false,
                created_at: inspection.createdAt,
              }),
            });
            if (retryResp.ok) {
              const created = await retryResp.json();
              backendInspectionId = created.id;
              await updateInspectionSyncState(inspectionId, { backendId: backendInspectionId });
            } else {
              const msg = 'Permanent error after token refresh: ' + retryResp.status;
              await markInspectionDeadLetter(inspectionId, 'permanent', msg);
              return { success: false, error: msg };
            }
          } catch (retryErr: unknown) {
            const msg = retryErr instanceof Error ? retryErr.message : 'Error after token refresh';
            await markInspectionDeadLetter(inspectionId, 'permanent', msg);
            return { success: false, error: msg };
          }
        }
      } else if (err instanceof SyncConflictError) {
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
      } else if (err instanceof SyncPermanentError) {
        const msg = 'Permanent error: ' + err.message;
        await markInspectionDeadLetter(inspectionId, 'permanent', msg);
        return { success: false, error: msg };
      } else {
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
      const imageBlob = await prepareImageBlobForUpload(img.dataUrl);
      const formData = new FormData();
      formData.append('client_id', img.id);
      formData.append('image_role', img.imageRole);
      formData.append('quality_check_passed', String(img.qualityAssessment?.passed ?? true));
      formData.append('file', imageBlob, `${img.imageRole}.jpg`);
      const headers = getAuthHeaders(currentToken, img.id);
      delete headers['Content-Type'];
      const imgResp = await fetchWithRetry(
        `${API_BASE}/inspections/${backendInspectionId}/images`,
        {
          method: 'POST',
          headers,
          body: formData,
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

  // Step 3: Trigger automated OCR extraction & legal metrology rule evaluation, then finalize status
  if (allImagesSucceeded) {
    if (backendInspectionId) {
      try {
        await fetchWithRetry(
          `${API_BASE}/inspections/${backendInspectionId}/process`,
          {
            method: 'POST',
            headers: getAuthHeaders(currentToken),
          },
          {
            maxRetries: 2,
            onRetry: (attempt, delay, reason) => {
              console.warn('[Sync] Retrying inspection process (' + attempt + '): ' + reason);
            },
          }
        );
      } catch (procErr) {
        const errorMsg = procErr instanceof Error ? procErr.message : 'OCR processing failed';
        console.warn('[Sync] OCR processing failed:', procErr);
        await updateInspectionSyncState(inspectionId, {
          status: 'failed',
          failureCategory: 'transient',
          nextRetryAt: new Date(Date.now() + calculateBackoffWithJitter(currentRetries, 1000, 30000)).toISOString(),
          syncError: errorMsg,
        });
        return { success: false, error: errorMsg };
      }
    }

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
