import {
  BatchManifestRead,
  BatchSessionCreate,
  BatchSessionDetail,
  BatchSessionRead,
} from "../types/batch";
import { InspectionRead } from "../types/inspection";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getAuthHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const authToken =
    token ||
    (typeof window !== "undefined" ? localStorage.getItem("access_token") : null);
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  return headers;
}

/**
 * Creates a new warehouse batch inspection session.
 */
export async function createBatchSession(
  payload: BatchSessionCreate,
  token?: string
): Promise<BatchSessionRead> {
  const res = await fetch(`${API_BASE}/batches`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to create batch session: ${res.status} ${err}`);
  }
  return res.json();
}

/**
 * Lists warehouse batch sessions with live SKU compliance metrics.
 */
export async function listBatchSessions(
  statusFilter?: string,
  token?: string
): Promise<BatchSessionRead[]> {
  const url = `${API_BASE}/batches${statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : ""}`;
  const res = await fetch(url, {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    throw new Error(`Failed to list batch sessions: ${res.status}`);
  }
  return res.json();
}

/**
 * Retrieves detailed batch session information with SKU items.
 */
export async function getBatchSessionDetail(
  batchId: string,
  token?: string
): Promise<BatchSessionDetail> {
  const res = await fetch(`${API_BASE}/batches/${batchId}`, {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    throw new Error(`Failed to get batch session: ${res.status}`);
  }
  return res.json();
}

/**
 * Creates an inspection record pre-linked to an active warehouse batch session.
 */
export async function createBatchSKUInspection(
  batchId: string,
  commodityCategory: string = "general",
  token?: string
): Promise<InspectionRead> {
  const res = await fetch(`${API_BASE}/batches/${batchId}/inspections`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({
      commodity_category: commodityCategory,
      captured_offline: false,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to create batch SKU inspection: ${res.status} ${err}`);
  }
  return res.json();
}

/**
 * Completes a warehouse batch inspection session.
 */
export async function completeBatchSession(
  batchId: string,
  token?: string
): Promise<BatchSessionRead> {
  const res = await fetch(`${API_BASE}/batches/${batchId}/complete`, {
    method: "POST",
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    throw new Error(`Failed to complete batch session: ${res.status}`);
  }
  return res.json();
}

/**
 * Retrieves the consolidated audit manifest for the batch session.
 */
export async function getBatchManifest(
  batchId: string,
  token?: string
): Promise<BatchManifestRead> {
  const res = await fetch(`${API_BASE}/batches/${batchId}/manifest`, {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    throw new Error(`Failed to get batch manifest: ${res.status}`);
  }
  return res.json();
}
