export interface RulePackSummary {
  version: string;
  effective_from: string;
  effective_to?: string | null;
  source_citation: string;
  is_active: boolean;
  created_by?: string | null;
  created_at: string;
  rule_count: number;
}

export interface RulePackRule {
  rule_id: string;
  applies_to: string[];
  type: string;
  field?: string;
  citation: string;
  severity: "critical" | "major" | "moderate";
  note?: string;
  min_height_mm?: number;
  tolerance_percentage?: number;
  [key: string]: unknown;
}

export interface RulePackDetail {
  version: string;
  effective_from: string;
  effective_to?: string | null;
  source_citation: string;
  is_active: boolean;
  created_by?: string | null;
  created_at: string;
  rules_json: {
    rule_pack_version: string;
    effective_from: string;
    effective_to?: string | null;
    source_citation: string;
    rules: RulePackRule[];
  };
}

export interface RuleDiffItem {
  id: string;
  type: "added" | "modified" | "deprecated";
  rule_id: string;
  title: string;
  citation: string;
  description: string;
  before?: string;
  after?: string;
}
