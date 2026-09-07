export interface BatchSKUItem {
  inspection_id: string;
  status: string;
  commodity_category?: string | null;
  created_at: string;
  violations_count: number;
  is_compliant: boolean;
  mrp?: string | null;
  net_quantity?: string | null;
  commodity_name?: string | null;
}

export interface BatchSessionRead {
  id: string;
  officer_id: string;
  session_name: string;
  premises_name?: string | null;
  premises_address?: string | null;
  region?: string | null;
  status: "active" | "completed" | "archived";
  notes?: string | null;
  created_at: string;
  completed_at?: string | null;
  total_skus_scanned: number;
  compliant_count: number;
  non_compliant_count: number;
  pending_count: number;
  compliance_rate_pct: number;
}

export interface BatchSessionDetail extends BatchSessionRead {
  items: BatchSKUItem[];
}

export interface BatchSessionCreate {
  session_name: string;
  premises_name?: string;
  premises_address?: string;
  region?: string;
  notes?: string;
}

export interface BatchManifestItem {
  item_seq: number;
  inspection_id: string;
  status: string;
  commodity_category?: string;
  mrp?: string;
  net_quantity?: string;
  manufacturer?: string;
  compliant: boolean;
  violations: Array<{
    rule_id: string;
    severity: string;
    description: string;
    citation: string;
  }>;
}

export interface BatchManifestRead {
  session_id: string;
  session_name: string;
  officer_id: string;
  premises_name?: string;
  premises_address?: string;
  region?: string;
  status: string;
  created_at: string;
  completed_at?: string;
  total_skus: number;
  compliant_skus: number;
  non_compliant_skus: number;
  compliance_rate_pct: number;
  total_violations: number;
  violations_by_rule: Record<string, number>;
  items: BatchManifestItem[];
}
