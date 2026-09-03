import { ReportFormat, ReportItem } from "../types/report";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function generateReport(
  inspectionId: string,
  format: ReportFormat = "pdf",
  token?: string
): Promise<ReportItem> {
  const url = `${API_BASE_URL}/api/v1/inspections/${inspectionId}/report?format=${format}`;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    method: "POST",
    headers,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to generate ${format} report`);
  }

  return res.json();
}

export async function listReports(
  inspectionId: string,
  token?: string
): Promise<ReportItem[]> {
  const url = `${API_BASE_URL}/api/v1/inspections/${inspectionId}/reports`;
  const headers: HeadersInit = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to list inspection reports");
  }

  return res.json();
}

export function getReportDownloadUrl(inspectionId: string, reportId: string): string {
  return `${API_BASE_URL}/api/v1/inspections/${inspectionId}/reports/${reportId}/file`;
}
