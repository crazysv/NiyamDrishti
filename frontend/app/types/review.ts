export type FieldReviewAction = "confirm" | "correct" | "mark_not_applicable";

export interface FieldReviewUpdate {
  action: FieldReviewAction;
  officer_override_value?: string | null;
  review_notes?: string | null;
}

export interface ExtractedFieldItem {
  id: string;
  inspection_id: string;
  source_image_id: string;
  field_type: string;
  raw_text: string | null;
  parsed_value: string | null;
  confidence: number;
  bounding_box: {
    x?: number;
    y?: number;
    w?: number;
    h?: number;
    [key: string]: unknown;
  };
  verdict: "pass" | "fail" | "needs_review" | "not_applicable";
  reviewed_by_officer: boolean;
  officer_override_value: string | null;
  created_at: string;
}

export interface FieldReviewResponse {
  field: ExtractedFieldItem;
  inspection_status: string;
  violations_count: number;
  audit_log_id: string;
  message: string;
}

export interface AuditLogItem {
  id: string;
  actor_user_id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  created_at: string;
}

export interface ReviewQueueItem {
  field_id: string;
  inspection_id: string;
  field_type: string;
  field_label: string;
  raw_text: string | null;
  parsed_value: string | null;
  confidence: number;
  verdict: "pass" | "fail" | "needs_review" | "not_applicable";
  bounding_box: {
    x?: number;
    y?: number;
    w?: number;
    h?: number;
    [key: string]: unknown;
  };
  source_image_id: string;
  source_image_url: string;
  flag_reason: string;
  reviewed_by_officer: boolean;
  officer_override_value: string | null;
  violations: Array<{
    id: string;
    rule_id: string;
    description: string;
    severity: string;
    citation?: string | null;
  }>;
}

export interface InspectionReviewQueue {
  inspection_id: string;
  overall_status: string;
  total_fields: number;
  pending_review_count: number;
  completed_review_count: number;
  items: ReviewQueueItem[];
}

export interface BatchFieldReviewItem {
  field_id: string;
  action: "confirm" | "override" | "mark_not_applicable";
  officer_override_value?: string | null;
  officer_notes?: string | null;
}

export interface BatchFieldReviewRequest {
  items: BatchFieldReviewItem[];
}

export interface BatchFieldReviewResponse {
  inspection_id: string;
  inspection_status: string;
  reviewed_count: number;
  violations_count: number;
  updated_fields: ExtractedFieldItem[];
  audit_log_ids: string[];
  message: string;
}

export interface ReviewHistoryItem {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  field_type: string;
  officer_id: string;
  officer_name: string;
  officer_role: string;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  created_at: string;
}
