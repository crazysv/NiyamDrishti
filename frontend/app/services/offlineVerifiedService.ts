import type { InspectionEvidence, EvidenceItem } from "@/app/types/evidence";

export interface OcrLine {
  text: string;
  confidence: number;
  bbox: { x0: number; y0: number; x1: number; y1: number };
  words?: Array<{ text: string; bbox: { x0: number; y0: number; x1: number; y1: number } }>;
}

export interface OfflineMatch {
  profile: OfflineSampleProfile;
  score: number;
  matchedAnchors: string[];
}

export interface OcrPanel {
  id: string;
  label: string;
  imageUrl: string;
  lines: OcrLine[];
  imageSize: { width: number; height: number };
}

export interface OfflineSampleProfile {
  id: "mother-dairy-full-cream" | "colgate-visible-white" | "wild-stone-after-shave";
  productName: string;
  category: string;
  anchors: string[];
  fields: Array<{
    fieldType: string;
    label: string;
    value: string;
    patterns: RegExp[];
    verdict: "pass" | "needs_review";
  }>;
  notes: string[];
}

export const offlineSampleProfiles: OfflineSampleProfile[] = [
  {
    id: "mother-dairy-full-cream",
    productName: "Mother Dairy Full Cream Milk",
    category: "packaged_food",
    anchors: ["mother dairy", "full cream", "500 ml"],
    fields: [
      { fieldType: "commodity_name", label: "PRODUCT", value: "Mother Dairy Full Cream Milk", patterns: [/mother\s*dairy/i, /full\s*cream/i], verdict: "pass" },
      { fieldType: "net_quantity", label: "NET QUANTITY", value: "500 ml", patterns: [/500\s*m[l1]/i], verdict: "pass" },
      { fieldType: "mrp", label: "MRP", value: "₹36 (inclusive of taxes)", patterns: [/(?:mrp|₹|rs\.?)\s*[:.]?\s*36(?:\.00)?/i], verdict: "needs_review" },
      { fieldType: "manufacturer_address", label: "MARKETED BY", value: "Mother Dairy Fruit & Vegetable Pvt. Ltd.", patterns: [/mother\s*dairy\s*fruit/i], verdict: "pass" },
      { fieldType: "consumer_care", label: "CONSUMER CARE", value: "1800-180-1018 · consumer.services@motherdairy.com", patterns: [/1800[-\s]?180[-\s]?1018/i], verdict: "pass" },
    ],
    notes: ["Local image evidence is shown for every declaration that was found.", "Items without a local text match remain in Review for officer confirmation."],
  },
  {
    id: "colgate-visible-white",
    productName: "Colgate Visible White Toothpaste",
    category: "cosmetic",
    anchors: ["colgate", "visible white", "240g"],
    fields: [
      { fieldType: "commodity_name", label: "PRODUCT", value: "Colgate Visible White Toothpaste", patterns: [/colgate/i, /visible\s*white/i], verdict: "pass" },
      { fieldType: "net_quantity", label: "NET QUANTITY", value: "240 g", patterns: [/240\s*g/i], verdict: "pass" },
      { fieldType: "mrp", label: "MRP", value: "₹378 (inclusive of taxes)", patterns: [/(?:mrp|₹|rs\.?)\s*[:.]?\s*378(?:\.00)?/i], verdict: "needs_review" },
      { fieldType: "manufacturer_address", label: "MANUFACTURER", value: "Colgate-Palmolive (India) Ltd.", patterns: [/colgate[-\s]?palmolive/i], verdict: "pass" },
      { fieldType: "country_of_origin", label: "COUNTRY OF ORIGIN", value: "Made in India", patterns: [/made\s*in\s*india/i], verdict: "pass" },
    ],
    notes: ["Local image evidence is shown for every declaration that was found.", "Items without a local text match remain in Review for officer confirmation."],
  },
  {
    id: "wild-stone-after-shave",
    productName: "Wild Stone Ultra Sensual After Shave Lotion",
    category: "cosmetic",
    anchors: ["wild stone", "after shave", "100 ml"],
    fields: [
      { fieldType: "commodity_name", label: "PRODUCT", value: "Wild Stone Ultra Sensual After Shave Lotion", patterns: [/wild\s*stone/i, /after\s*shave/i], verdict: "pass" },
      { fieldType: "net_quantity", label: "NET CONTENT", value: "100 ml", patterns: [/100\s*m[l1]/i], verdict: "pass" },
      { fieldType: "mrp", label: "MRP", value: "₹200 (inclusive of taxes)", patterns: [/(?:mrp|₹|rs\.?)\s*[:.]?\s*200(?:\.00)?/i], verdict: "needs_review" },
      { fieldType: "mfg_date", label: "MFG. DATE", value: "06/2026", patterns: [/06\s*[/.-]\s*2026/i], verdict: "pass" },
      { fieldType: "consumer_care", label: "CONSUMER CARE", value: "+91 33 4014 2100 · care@mcroe.com", patterns: [/\+?91\s*33\s*4014\s*2100\s*.*care@mcroe\.com/i], verdict: "pass" },
    ],
    notes: ["Local image evidence is shown for every declaration that was found.", "Items without a local text match remain in Review for officer confirmation."],
  },
];

function normalise(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function anchorScore(anchor: string, text: string): number {
  const cleanAnchor = normalise(anchor);
  if (text.includes(cleanAnchor)) return 1;
  const tokens = cleanAnchor.split(" ").filter(Boolean);
  return tokens.length ? tokens.filter((token) => text.includes(token)).length / tokens.length : 0;
}

export function matchOfflineSample(lines: OcrLine[]): OfflineMatch | null {
  const text = normalise(lines.map((line) => line.text).join(" "));
  const candidates = offlineSampleProfiles.map((profile) => {
    const matches = profile.anchors.filter((anchor) => anchorScore(anchor, text) >= 0.99);
    const score = profile.anchors.reduce((total, anchor) => total + anchorScore(anchor, text), 0) / profile.anchors.length;
    return { profile, score, matchedAnchors: matches };
  }).sort((a, b) => b.score - a.score);

  const best = candidates[0];
  return best && best.score >= 0.66 && best.matchedAnchors.length >= 2 ? best : null;
}

function matches(pattern: RegExp, value: string): boolean {
  return new RegExp(pattern.source, pattern.flags.replace(/[gy]/g, "")).test(value);
}

function exactWordBox(line: OcrLine, pattern: RegExp): OcrLine["bbox"] | undefined {
  const words = line.words || [];
  for (let start = 0; start < words.length; start += 1) {
    for (let end = start + 1; end <= Math.min(words.length, start + 6); end += 1) {
      const matchedWords = words.slice(start, end);
      if (!matches(pattern, matchedWords.map((word) => word.text).join(" "))) continue;
      return {
        x0: Math.min(...matchedWords.map((word) => word.bbox.x0)),
        y0: Math.min(...matchedWords.map((word) => word.bbox.y0)),
        x1: Math.max(...matchedWords.map((word) => word.bbox.x1)),
        y1: Math.max(...matchedWords.map((word) => word.bbox.y1)),
      };
    }
  }
  return undefined;
}

function lineFor(patterns: RegExp[], panels: OcrPanel[]): { line: OcrLine; panel: OcrPanel } | undefined {
  // Patterns are deliberately ordered from the declaration value to its label.
  // Search every panel for the more specific value first: otherwise an early,
  // broad "NET CONTENT" label can win over a later and accurately boxed "100 ml".
  for (const pattern of patterns) {
    for (const panel of panels) {
      for (const line of panel.lines) {
        if (!matches(pattern, line.text)) continue;
        const preciseBox = exactWordBox(line, pattern);
        return { line: preciseBox ? { ...line, bbox: preciseBox } : line, panel };
      }
    }
  }
  return undefined;
}

export function buildOfflineEvidence(match: OfflineMatch, panels: OcrPanel[], inspectionId: string): InspectionEvidence {
  const primaryPanel = panels[0];
  const items: EvidenceItem[] = match.profile.fields.map((field, index) => {
    const source = lineFor(field.patterns, panels);
    const bbox = source?.line.bbox || { x0: 0, y0: 0, x1: 0, y1: 0 };
    const width = Math.max(0, bbox.x1 - bbox.x0);
    const height = Math.max(0, bbox.y1 - bbox.y0);
    return {
      item_id: `R${String(index + 1).padStart(2, "0")}`,
      field_id: `offline-${match.profile.id}-${field.fieldType}`,
      field_type: field.fieldType,
      field_label: field.label,
      raw_text: source?.line.text || "No matching declaration was located in the captured panels.",
      parsed_value: field.value,
      confidence: source ? Math.min(0.99, Math.max(0.5, source.line.confidence / 100)) : 0,
      verdict: source ? field.verdict : "needs_review",
      bounding_box: {
        x: bbox.x0,
        y: bbox.y0,
        w: width,
        h: height,
        left_pct: source?.panel.imageSize.width ? (bbox.x0 / source.panel.imageSize.width) * 100 : 0,
        top_pct: source?.panel.imageSize.height ? (bbox.y0 / source.panel.imageSize.height) * 100 : 0,
        width_pct: source?.panel.imageSize.width ? (width / source.panel.imageSize.width) * 100 : 0,
        height_pct: source?.panel.imageSize.height ? (height / source.panel.imageSize.height) * 100 : 0,
      },
      source_image_id: source?.panel.id || primaryPanel.id,
      source_image_url: source?.panel.imageUrl || primaryPanel.imageUrl,
      is_calibrated: false,
      review_reason: source ? (field.verdict === "needs_review" ? "The detected declaration needs officer confirmation before a compliance decision." : null) : "No readable local declaration was found in any captured panel.",
      violations: [],
    };
  });
  const passed = items.filter((item) => item.verdict === "pass").length;
  const review = items.length - passed;
  return {
    inspection_id: inspectionId,
    product_name: match.profile.productName,
    commodity_category: match.profile.category,
    overall_status: "needs_review",
    rule_pack_version: "2026.02.01",
    officer_id: "offline-local-check",
    officer_name: "Local inspection",
    primary_image_url: primaryPanel.imageUrl,
    primary_image_dimensions: primaryPanel.imageSize,
    image_panels: panels.map((panel) => ({ id: panel.id, url: panel.imageUrl, label: panel.label })),
    items,
    stats: { total: items.length, passed, review, failed: 0 },
  };
}

export async function recogniseOfflineImage(image: string, onProgress?: (progress: number) => void): Promise<{ lines: OcrLine[]; imageSize: { width: number; height: number } }> {
  const [{ createWorker }, dimensions] = await Promise.all([
    import("tesseract.js"),
    new Promise<{ width: number; height: number }>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
      img.onerror = () => reject(new Error("Could not read the captured image."));
      img.src = image;
    }),
  ]);
  const worker = await createWorker("eng", 1, {
    workerPath: "/ocr/worker.min.js",
    corePath: "/ocr/core",
    langPath: "/ocr/lang",
    logger: (message) => onProgress?.(Math.round(message.progress * 100)),
  });
  try {
    const { data } = await worker.recognize(image, {}, { blocks: true });
    const lines: OcrLine[] = (data.blocks || []).flatMap((block) =>
      block.paragraphs.flatMap((paragraph) => paragraph.lines.map((line) => ({
        text: line.text,
        confidence: line.confidence,
        bbox: line.bbox,
        words: line.words.map((word) => ({ text: word.text, bbox: word.bbox })),
      }))),
    ).filter((line) => line.text.trim());
    return { lines, imageSize: dimensions };
  } finally {
    await worker.terminate();
  }
}

export function getOfflineSampleNotes(profile: OfflineSampleProfile): string[] {
  return profile.notes;
}
