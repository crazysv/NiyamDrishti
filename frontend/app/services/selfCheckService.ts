import {
  SelfCheckCreatePayload,
  SelfCheckInspection,
  SelfCheckScorecard,
  SelfCheckSummary,
} from "../types/selfCheck";

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
 * Creates a new manufacturer pre-distribution compliance self-check (E3-06).
 */
export async function createSelfCheck(
  payload: SelfCheckCreatePayload,
  token?: string
): Promise<SelfCheckInspection> {
  const res = await fetch(`${API_BASE}/self-check/inspections`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to create self-check: ${res.status} ${err}`);
  }
  return res.json();
}

/**
 * Lists self-check audits conducted by the authenticated manufacturer.
 */
export async function listSelfChecks(
  skip = 0,
  limit = 20,
  token?: string
): Promise<SelfCheckInspection[]> {
  const res = await fetch(
    `${API_BASE}/self-check/inspections?skip=${skip}&limit=${limit}`,
    {
      headers: getAuthHeaders(token),
    }
  );
  if (!res.ok) {
    throw new Error(`Failed to list self-checks: ${res.status}`);
  }
  return res.json();
}

/**
 * Retrieves a single self-check inspection.
 */
export async function getSelfCheck(
  id: string,
  token?: string
): Promise<SelfCheckInspection> {
  const res = await fetch(`${API_BASE}/self-check/inspections/${id}`, {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    throw new Error(`Failed to get self-check: ${res.status}`);
  }
  return res.json();
}

/**
 * Retrieves the constructive pre-distribution compliance scorecard and remediation advice.
 */
export async function getSelfCheckScorecard(
  id: string,
  token?: string
): Promise<SelfCheckScorecard> {
  const res = await fetch(`${API_BASE}/self-check/inspections/${id}/scorecard`, {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    throw new Error(`Failed to get self-check scorecard: ${res.status}`);
  }
  return res.json();
}

/**
 * Retrieves aggregate metrics for the manufacturer packaging portal.
 */
export async function getSelfCheckSummary(token?: string): Promise<SelfCheckSummary> {
  const res = await fetch(`${API_BASE}/self-check/summary`, {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    throw new Error(`Failed to get self-check summary: ${res.status}`);
  }
  return res.json();
}
