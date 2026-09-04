import {
  AnalyticsSummary,
  ComplianceTrends,
  ViolationHotspots,
  OfficerThroughput,
} from "../types/analytics";
import { API_BASE } from "../utils/apiConfig";

function getAuthToken(explicitToken?: string): string | null {
  if (explicitToken) return explicitToken;
  if (typeof window !== "undefined") {
    return localStorage.getItem("access_token") || localStorage.getItem("token") || null;
  }
  return null;
}

export async function fetchAnalyticsSummary(token?: string): Promise<AnalyticsSummary> {
  const authToken = getAuthToken(token);
  const headers: Record<string, string> = {};
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

  const res = await fetch(`${API_BASE}/analytics/summary`, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch analytics summary: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function fetchComplianceTrends(
  params?: {
    startDate?: string;
    endDate?: string;
    category?: string;
    region?: string;
  },
  token?: string
): Promise<ComplianceTrends> {
  const authToken = getAuthToken(token);
  const headers: Record<string, string> = {};
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

  const queryParams = new URLSearchParams();
  if (params?.startDate) queryParams.set("start_date", params.startDate);
  if (params?.endDate) queryParams.set("end_date", params.endDate);
  if (params?.category) queryParams.set("category", params.category);
  if (params?.region) queryParams.set("region", params.region);

  const url = `${API_BASE}/analytics/compliance-trends${queryParams.toString() ? `?${queryParams.toString()}` : ""}`;
  const res = await fetch(url, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch compliance trends: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function fetchViolationHotspots(
  limit: number = 10,
  token?: string
): Promise<ViolationHotspots> {
  const authToken = getAuthToken(token);
  const headers: Record<string, string> = {};
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

  const res = await fetch(`${API_BASE}/analytics/violation-hotspots?limit=${limit}`, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch violation hotspots: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function fetchOfficerThroughput(token?: string): Promise<OfficerThroughput> {
  const authToken = getAuthToken(token);
  const headers: Record<string, string> = {};
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

  const res = await fetch(`${API_BASE}/analytics/officer-throughput`, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch officer throughput: ${res.status} ${errorText}`);
  }
  return res.json();
}
