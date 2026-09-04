export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
  left_pct: number;
  top_pct: number;
  width_pct: number;
  height_pct: number;
}

export interface EvidenceViolation {
  id: string;
  rule_id: string;
  description: string;
  citation?: string | null;
  severity: "minor" | "major" | "critical";
}

export interface MeasuredDimension {
  height_mm?: number | null;
  scale_mm_per_px?: number | null;
  pdp_ratio?: number | null;
  is_calibrated?: boolean;
  warning?: string | null;
}

export interface EvidenceItem {
  item_id: string;
  field_id: string;
  field_type: string;
  field_label: string;
  raw_text?: string | null;
  parsed_value?: string | null;
  confidence: number;
  verdict: "pass" | "needs_review" | "fail";
  bounding_box: BoundingBox;
  source_image_id: string;
  source_image_url: string;
  is_calibrated: boolean;
  measured_dimension?: MeasuredDimension | null;
  violations: EvidenceViolation[];
}

export interface EvidenceImage {
  id: string;
  image_role: string;
  storage_url: string;
  width_px?: number | null;
  height_px?: number | null;
  calibration_scale_mm_per_px?: number | null;
}

export interface InspectionEvidence {
  inspection_id: string;
  product_name: string;
  commodity_category: string;
  overall_status: "compliant" | "violations_found" | "needs_review";
  rule_pack_version: string;
  officer_id: string;
  officer_name?: string | null;
  primary_image_url?: string | null;
  primary_image_dimensions?: { width: number; height: number } | null;
  images?: EvidenceImage[];
  items: EvidenceItem[];
  stats: {
    total: number;
    passed: number;
    review: number;
    failed: number;
  };
}
