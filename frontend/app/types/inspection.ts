export interface InspectionSummary {
  id: string;
  officer_id: string;
  officer_name?: string | null;
  status: "draft" | "sync_pending" | "needs_review" | "completed" | "syncing" | "synced" | "failed" | "dead_letter";
  commodity_category?: string | null;
  rule_pack_version: string;
  region?: string | null;
  captured_offline: boolean;
  created_at: string;
  updated_at: string;
  violations_count: number;
  fields_count: number;
  images_count: number;
  thumbnail_url?: string | null;
  overall_verdict: "compliant" | "non_compliant" | "needs_review";
}

export interface InspectionListResponse {
  items: InspectionSummary[];
  total: number;
  skip: number;
  limit: number;
}

export interface InspectionSearchParams {
  officer_id?: string;
  officer_name?: string;
  date_from?: string;
  date_to?: string;
  region?: string;
  commodity_category?: string;
  status?: string;
  violation_type?: string;
  has_violations?: boolean;
  product_query?: string;
  skip?: number;
  limit?: number;
}

export interface InspectionRead {
  id: string;
  officer_id: string;
  status: string;
  commodity_category?: string | null;
  rule_pack_version: string;
  is_self_check: boolean;
  region?: string | null;
  captured_offline: boolean;
  created_at: string;
  updated_at: string;
  synced_at?: string | null;
}
