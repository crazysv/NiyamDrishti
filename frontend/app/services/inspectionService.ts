import { InspectionListResponse, InspectionSearchParams } from "../types/inspection";
import { API_BASE } from "../utils/apiConfig";

/**
 * Searches and lists inspections with multi-parameter filtering (SRCH-01).
 */
export async function searchInspections(
  params: InspectionSearchParams = {},
  token?: string
): Promise<InspectionListResponse> {
  const query = new URLSearchParams();

  if (params.officer_id) query.append("officer_id", params.officer_id);
  if (params.officer_name) query.append("officer_name", params.officer_name);
  if (params.date_from) query.append("date_from", params.date_from);
  if (params.date_to) query.append("date_to", params.date_to);
  if (params.region) query.append("region", params.region);
  if (params.commodity_category) query.append("commodity_category", params.commodity_category);
  if (params.status) query.append("status", params.status);
  if (params.violation_type) query.append("violation_type", params.violation_type);
  if (typeof params.has_violations === "boolean") {
    query.append("has_violations", String(params.has_violations));
  }
  if (params.product_query) query.append("product_query", params.product_query);
  if (typeof params.skip === "number") query.append("skip", String(params.skip));
  if (typeof params.limit === "number") query.append("limit", String(params.limit));

  const url = `${API_BASE}/inspections${query.toString() ? `?${query.toString()}` : ""}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const authToken =
    token ||
    (typeof window !== "undefined" ? localStorage.getItem("access_token") : null);

  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  const res = await fetch(url, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch inspections: ${res.status} ${errorText}`);
  }

  return res.json();
}
