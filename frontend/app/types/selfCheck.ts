export interface SelfCheckField {
  id: string;
  field_type: string;
  raw_text?: string | null;
  parsed_value?: string | null;
  confidence: number;
  verdict: string;
}

export interface SelfCheckImage {
  id: string;
  image_role: string;
  storage_url: string;
}

export interface SelfCheckViolation {
  id: string;
  rule_id: string;
  rule_pack_version: string;
  description: string;
  citation?: string | null;
  severity: string;
}

export interface SelfCheckCreatePayload {
  commodity_category?: string;
  brand_name?: string;
  product_name?: string;
  batch_or_lot_number?: string;
  pdp_area_sq_cm?: number;
  rule_pack_version?: string;
}

export interface SelfCheckRemediationItem {
  rule_id: string;
  citation?: string | null;
  severity: string;
  issue: string;
  remedial_action: string;
  field_name?: string | null;
}

export interface SelfCheckScorecard {
  inspection_id: string;
  brand_name?: string | null;
  product_name?: string | null;
  commodity_category: string;
  status: string;
  overall_readiness: 'MARKET_READY' | 'ACTION_REQUIRED' | 'CRITICAL_DEFICIENCIES';
  total_declarations_checked: number;
  compliant_count: number;
  violation_count: number;
  readiness_percentage: number;
  remediations: SelfCheckRemediationItem[];
  created_at: string;
  disclaimer: string;
}

export interface SelfCheckInspection {
  id: string;
  user_id: string;
  commodity_category?: string | null;
  rule_pack_version: string;
  status: string;
  is_self_check: boolean;
  created_at: string;
  updated_at: string;
  images: SelfCheckImage[];
  fields: SelfCheckField[];
  violations: SelfCheckViolation[];
}

export interface SelfCheckSummary {
  total_self_checks: number;
  market_ready_count: number;
  action_required_count: number;
  first_pass_rate: number;
  common_deficiencies: Array<{
    rule_id: string;
    citation?: string | null;
    description: string;
    count: number;
  }>;
}
