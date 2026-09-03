export interface AnalyticsSummary {
  total_inspections: number;
  completed_inspections: number;
  needs_review_inspections: number;
  draft_inspections: number;
  compliant_inspections: number;
  violation_inspections: number;
  overall_compliance_rate: number;
  total_violations: number;
  critical_violations: number;
  major_violations: number;
  moderate_violations: number;
  total_audit_overrides: number;
  active_officers_count: number;
}

export interface ComplianceTrendPoint {
  date: string;
  total_inspections: number;
  compliant_count: number;
  violation_count: number;
  compliance_rate: number;
}

export interface ComplianceTrends {
  points: ComplianceTrendPoint[];
  period_start?: string | null;
  period_end?: string | null;
}

export interface RuleViolationHotspot {
  rule_id: string;
  citation?: string | null;
  description: string;
  count: number;
  severity: string;
}

export interface CategoryViolationHotspot {
  commodity_category: string;
  total_inspections: number;
  violations_count: number;
  compliance_rate: number;
}

export interface RegionViolationHotspot {
  region: string;
  total_inspections: number;
  violations_count: number;
  compliance_rate: number;
}

export interface ViolationHotspots {
  by_rule: RuleViolationHotspot[];
  by_category: CategoryViolationHotspot[];
  by_region: RegionViolationHotspot[];
}

export interface OfficerThroughputItem {
  officer_id: string;
  officer_name: string;
  email: string;
  region?: string | null;
  total_inspections: number;
  completed_inspections: number;
  needs_review_inspections: number;
  human_overrides_count: number;
  last_inspection_at?: string | null;
}

export interface OfficerThroughput {
  officers: OfficerThroughputItem[];
  total_active_officers: number;
}
