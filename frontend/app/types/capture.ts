import { QualityAssessment } from "@/app/utils/qualityGate";

export type ImageRole = "front_pdp" | "back_panel" | "side_panel" | "sticker";

export type CommodityCategory =
  | "general"
  | "packaged_food"
  | "electronics"
  | "pan_masala"
  | "medical_device";

export interface CapturedImage {
  id: string;
  role: ImageRole;
  dataUrl: string;
  capturedAt: string;
  fileName?: string;
  fileSize?: number;
  width?: number;
  height?: number;
  isAuthoritative?: boolean;
  qualityAssessment?: QualityAssessment;
}

export interface SlotConfig {
  role: ImageRole;
  slotCode: string;
  label: string;
  isRequired: boolean;
  hint: string;
}

export const CAPTURE_SLOTS: SlotConfig[] = [
  {
    role: "front_pdp",
    slotCode: "E01",
    label: "FRONT PDP",
    isRequired: true,
    hint: "Principal Display Panel with product name, net quantity & MRP",
  },
  {
    role: "back_panel",
    slotCode: "E02",
    label: "BACK / SIDE",
    isRequired: true,
    hint: "Back or side panel with manufacturer details & consumer care",
  },
  {
    role: "sticker",
    slotCode: "E03",
    label: "MRP STICKER",
    isRequired: false,
    hint: "Secondary sticker or price alteration tag (if applicable)",
  },
];
