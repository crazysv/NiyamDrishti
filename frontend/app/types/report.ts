export type ReportFormat = "pdf" | "editable";

export interface ReportItem {
  id: string;
  inspection_id: string;
  format: ReportFormat;
  storage_url: string;
  download_url: string;
  generated_by: string;
  generated_at: string;
}
