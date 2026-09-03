import {
  AnalyticsSummary,
  ComplianceTrends,
  ViolationHotspots,
  OfficerThroughput,
} from "../types/analytics";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function fetchAnalyticsSummary(token?: string): Promise<AnalyticsSummary> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

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
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

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
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/analytics/violation-hotspots?limit=${limit}`, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch violation hotspots: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function fetchOfficerThroughput(token?: string): Promise<OfficerThroughput> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/analytics/officer-throughput`, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch officer throughput: ${res.status} ${errorText}`);
  }
  return res.json();
}
