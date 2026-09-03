import {
  AuditLogItem,
  FieldReviewUpdate,
  FieldReviewResponse,
  InspectionReviewQueue,
} from "../types/review";
import { API_BASE } from "../utils/apiConfig";

export async function fetchReviewQueue(
  inspectionId: string,
  token?: string
): Promise<InspectionReviewQueue> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/inspections/${inspectionId}/review-queue`, {
    headers,
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch review queue: ${res.status} ${errorText}`);
  }

  return res.json();
}

export async function submitFieldReview(
  inspectionId: string,
  fieldId: string,
  update: FieldReviewUpdate,
  token?: string
): Promise<FieldReviewResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(
    `${API_BASE}/inspections/${inspectionId}/fields/${fieldId}`,
    {
      method: "PATCH",
      headers,
      body: JSON.stringify(update),
    }
  );

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to review field: ${res.status} ${errorText}`);
  }

  return res.json();
}

export async function fetchAuditLogs(
  inspectionId: string,
  token?: string
): Promise<AuditLogItem[]> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/inspections/${inspectionId}/audit-logs`, {
    headers,
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch audit logs: ${res.status} ${errorText}`);
  }

  return res.json();
}

export async function submitBatchFieldReview(
  inspectionId: string,
  request: { items: Array<{ field_id: string; action: "confirm" | "override" | "mark_not_applicable"; officer_override_value?: string | null; officer_notes?: string | null }> },
  token?: string
) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/inspections/${inspectionId}/fields/batch-review`, {
    method: "POST",
    headers,
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to submit batch review: ${res.status} ${errorText}`);
  }

  return res.json();
}

export async function fetchReviewHistory(
  inspectionId: string,
  token?: string
) {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/inspections/${inspectionId}/review-history`, {
    headers,
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch review history: ${res.status} ${errorText}`);
  }

  return res.json();
}
