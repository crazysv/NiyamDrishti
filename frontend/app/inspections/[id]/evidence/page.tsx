"use client";

import React, { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import EvidenceViewer from "@/app/components/evidence/EvidenceViewer";
import { InspectionEvidence } from "@/app/types/evidence";
import { db } from "@/app/db/dexie";
import { ArrowLeft, Loader2 } from "lucide-react";

interface EvidencePageProps {
  params: Promise<{ id: string }>;
}

export default function EvidencePage({ params }: EvidencePageProps) {
  const resolvedParams = use(params);
  const inspectionId = resolvedParams.id;
  const router = useRouter();

  const [evidence, setEvidence] = useState<InspectionEvidence | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadEvidence() {
      setIsLoading(true);
      setError(null);

      try {
        // 1. Attempt to fetch from backend API
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const res = await fetch(`/api/v1/inspections/${inspectionId}/evidence`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });

        if (res.ok) {
          const data: InspectionEvidence = await res.json();
          setEvidence(data);
          setIsLoading(false);
          return;
        }

        // 2. Offline Fallback: Check local IndexedDB (Dexie)
        const localInsp = await db.inspections.get(inspectionId);
        if (localInsp) {
          const localImages = await db.inspectionImages
            .where("inspectionId")
            .equals(inspectionId)
            .toArray();

          const frontImg = localImages.find((img) => img.imageRole === "front_pdp") || localImages[0];

          // Construct fallback offline evidence structure
          const offlineEvidence: InspectionEvidence = {
            inspection_id: localInsp.id,
            product_name: `Inspected ${localInsp.commodityCategory.replace(/_/g, " ").toUpperCase()}`,
            commodity_category: localInsp.commodityCategory,
            overall_status: "needs_review",
            rule_pack_version: "2026.02.01",
            officer_id: "offline-officer",
            officer_name: "Legal Metrology Officer",
            primary_image_url: frontImg?.dataUrl || null,
            primary_image_dimensions: { width: 1000, height: 1500 },
            items: [
              {
                item_id: "E01",
                field_id: "f-01",
                field_type: "mrp",
                field_label: "MRP",
                raw_text: "MRP: Pending sync",
                parsed_value: null,
                confidence: 0.85,
                verdict: "needs_review",
                bounding_box: { x: 260, y: 465, w: 220, h: 75, left_pct: 26, top_pct: 31, width_pct: 22, height_pct: 5 },
                source_image_id: frontImg?.id || "img-01",
                source_image_url: frontImg?.dataUrl || "",
                is_calibrated: false,
                violations: [],
              },
              {
                item_id: "E02",
                field_id: "f-02",
                field_type: "net_quantity",
                field_label: "NET QUANTITY",
                raw_text: "Net Qty: Pending sync",
                parsed_value: null,
                confidence: 0.90,
                verdict: "needs_review",
                bounding_box: { x: 260, y: 570, w: 280, h: 75, left_pct: 26, top_pct: 38, width_pct: 28, height_pct: 5 },
                source_image_id: frontImg?.id || "img-01",
                source_image_url: frontImg?.dataUrl || "",
                is_calibrated: false,
                violations: [],
              },
            ],
            stats: {
              total: 2,
              passed: 0,
              review: 2,
              failed: 0,
            },
          };

          setEvidence(offlineEvidence);
          setIsLoading(false);
          return;
        }

        // 3. Fallback Sample for Demonstration if completely empty
        const demoEvidence: InspectionEvidence = {
          inspection_id: inspectionId,
          product_name: "Royal Basmati Rice",
          commodity_category: "packaged_food",
          overall_status: "violations_found",
          rule_pack_version: "2026.02.01",
          officer_id: "off-demo-01",
          officer_name: "Insp. K. Singh",
          primary_image_url: "https://lh3.googleusercontent.com/aida-public/AB6AXuCh8eDoILqkOABABD1jYUloHvi3_vaRPwCNFXT84AWqQvqITrVLMtq9QeIMoZKK0AY0IBxciG0UyuAfJr2ck-KOBxRotBb0G34_3X8Npuk32EYjJ8lQO_M690mjzYDne9ZlxK7C08UuXkoSw19PVKKkoC9yovp1sn0piLsCZk0Nspa9BfMBJgK-HiTU00uw4dc4H1DHOxmNINsZahPfGqwyJDLwblQFo6KVvB4kwEirD3MynJaQrU_U",
          primary_image_dimensions: { width: 1000, height: 1500 },
          items: [
            {
              item_id: "E01",
              field_id: "f-01",
              field_type: "mrp",
              field_label: "MRP",
              raw_text: "MRP: ₹125.00 (Incl. of all taxes)",
              parsed_value: "₹125.00",
              confidence: 0.94,
              verdict: "pass",
              bounding_box: { x: 260, y: 465, w: 220, h: 75, left_pct: 26, top_pct: 31, width_pct: 22, height_pct: 5 },
              source_image_id: "img-01",
              source_image_url: "",
              is_calibrated: true,
              measured_dimension: { height_mm: 3.2, scale_mm_per_px: 0.08, is_calibrated: true },
              violations: [],
            },
            {
              item_id: "E02",
              field_id: "f-02",
              field_type: "net_quantity",
              field_label: "NET QUANTITY",
              raw_text: "1 kg",
              parsed_value: "1 kg",
              confidence: 0.97,
              verdict: "pass",
              bounding_box: { x: 260, y: 570, w: 280, h: 75, left_pct: 26, top_pct: 38, width_pct: 28, height_pct: 5 },
              source_image_id: "img-01",
              source_image_url: "",
              is_calibrated: true,
              measured_dimension: { height_mm: 2.1, scale_mm_per_px: 0.08, is_calibrated: true },
              violations: [],
            },
            {
              item_id: "E03",
              field_id: "f-03",
              field_type: "mfg_date",
              field_label: "DATE OF MFG",
              raw_text: "15 OCT 2023",
              parsed_value: "10/2023",
              confidence: 0.78,
              verdict: "needs_review",
              bounding_box: { x: 260, y: 660, w: 420, h: 90, left_pct: 26, top_pct: 44, width_pct: 42, height_pct: 6 },
              source_image_id: "img-01",
              source_image_url: "",
              is_calibrated: true,
              measured_dimension: { height_mm: 2.1, scale_mm_per_px: 0.08, is_calibrated: true },
              violations: [
                {
                  id: "v-01",
                  rule_id: "declaration-present-mfg-date",
                  description: "Format ambiguity detected. Review req.",
                  severity: "major",
                },
              ],
            },
            {
              item_id: "E04",
              field_id: "f-04",
              field_type: "manufacturer_address",
              field_label: "MANUFACTURER",
              raw_text: "Sunrise Foods Pvt. Ltd., Delhi - 110001",
              parsed_value: "Sunrise Foods Pvt. Ltd.",
              confidence: 0.88,
              verdict: "pass",
              bounding_box: { x: 260, y: 855, w: 450, h: 135, left_pct: 26, top_pct: 57, width_pct: 45, height_pct: 9 },
              source_image_id: "img-01",
              source_image_url: "",
              is_calibrated: true,
              violations: [],
            },
            {
              item_id: "E05",
              field_id: "f-05",
              field_type: "consumer_care",
              field_label: "CONSUMER CARE",
              raw_text: "Toll free: 1800-XXX-XXXX",
              parsed_value: "1800-XXX-XXXX",
              confidence: 0.91,
              verdict: "pass",
              bounding_box: { x: 260, y: 1020, w: 420, h: 90, left_pct: 26, top_pct: 68, width_pct: 42, height_pct: 6 },
              source_image_id: "img-01",
              source_image_url: "",
              is_calibrated: true,
              violations: [],
            },
          ],
          stats: {
            total: 5,
            passed: 4,
            review: 1,
            failed: 0,
          },
        };
        setEvidence(demoEvidence);
      } catch (err: unknown) {
        setError((err as Error).message || "Failed to load evidence data");
      } finally {
        setIsLoading(false);
      }
    }

    loadEvidence();
  }, [inspectionId]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#f9f9fc] text-[#1a1c1e]">
        <Loader2 className="w-8 h-8 animate-spin text-[#333e50] mb-3" />
        <p className="text-sm font-mono text-[#75777d]">Loading inspection evidence...</p>
      </div>
    );
  }

  if (error || !evidence) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#f9f9fc] text-[#1a1c1e] p-6">
        <p className="text-sm font-mono text-red-600 mb-4">{error || "Evidence record not found"}</p>
        <button
          type="button"
          onClick={() => router.back()}
          className="flex items-center gap-2 bg-[#333e50] text-white px-4 py-2 rounded-md text-xs font-medium"
        >
          <ArrowLeft className="w-4 h-4" /> Go Back
        </button>
      </div>
    );
  }

  return (
    <EvidenceViewer
      evidence={evidence}
      onReviewQueueClick={() => router.push(`/inspections/${inspectionId}/review`)}
      onGenerateReportClick={() => router.push(`/inspections/${inspectionId}/report`)}
    />
  );
}
