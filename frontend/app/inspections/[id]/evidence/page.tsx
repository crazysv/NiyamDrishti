"use client";

import React, { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import EvidenceViewer from "@/app/components/evidence/EvidenceViewer";
import { InspectionEvidence } from "@/app/types/evidence";
import { db } from "@/app/db/dexie";
import { ArrowLeft, Loader2 } from "lucide-react";
import { API_BASE } from "@/app/utils/apiConfig";

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
        const token =
          typeof window !== "undefined"
            ? localStorage.getItem("access_token") || localStorage.getItem("token")
            : null;

        let res: Response | null = null;
        try {
          res = await fetch(`${API_BASE}/inspections/${inspectionId}/evidence`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });

          if (res.ok) {
            const data: InspectionEvidence = await res.json();
            setEvidence(data);
            setIsLoading(false);
            return;
          }
        } catch (fetchErr) {
          console.warn("[EvidencePage] Network fetch failed, checking offline storage:", fetchErr);
        }

        // 2. Offline Fallback: Check local IndexedDB (Dexie) by local id or backendId
        let localInsp = await db.inspections.get(inspectionId);
        if (!localInsp) {
          localInsp = await db.inspections.where("backendId").equals(inspectionId).first();
        }

        if (localInsp) {
          const localImages = await db.inspectionImages
            .where("inspectionId")
            .equals(localInsp.id)
            .toArray();

          const frontImg = localImages.find((img) => img.imageRole === "front_pdp") || localImages[0];

          // Construct fallback offline evidence structure from local capture
          const offlineEvidence: InspectionEvidence = {
            inspection_id: localInsp.backendId || localInsp.id,
            product_name: `Inspected ${localInsp.commodityCategory.replace(/_/g, " ").toUpperCase()}`,
            commodity_category: localInsp.commodityCategory,
            overall_status: localInsp.status === "synced" ? "needs_review" : "needs_review",
            rule_pack_version: "2026.02.01",
            officer_id: "assigned_officer",
            officer_name: "Legal Metrology Officer",
            primary_image_url: frontImg?.dataUrl || null,
            primary_image_dimensions: { width: 1200, height: 1600 },
            items: [
              {
                item_id: "E01",
                field_id: "f-01",
                field_type: "commodity_name",
                field_label: "COMMODITY",
                raw_text: localInsp.commodityCategory.replace(/_/g, " ").toUpperCase(),
                parsed_value: localInsp.commodityCategory.replace(/_/g, " ").toUpperCase(),
                confidence: 0.95,
                verdict: "pass",
                bounding_box: { x: 200, y: 300, w: 600, h: 120, left_pct: 20, top_pct: 20, width_pct: 60, height_pct: 8 },
                source_image_id: frontImg?.id || "img-01",
                source_image_url: frontImg?.dataUrl || "",
                is_calibrated: false,
                violations: [],
              },
            ],
            stats: {
              total: 1,
              passed: 1,
              review: 0,
              failed: 0,
            },
          };

          setEvidence(offlineEvidence);
          setIsLoading(false);
          return;
        }

        // 3. Fallback Sample ONLY if explicitly demo or sample inspection
        if (inspectionId === "demo" || inspectionId === "sample") {
          const demoEvidence: InspectionEvidence = {
            inspection_id: inspectionId,
            product_name: "Royal Basmati Rice",
            commodity_category: "packaged_food",
            overall_status: "violations_found",
            rule_pack_version: "2026.02.01",
            officer_id: "off-demo-01",
            officer_name: "Insp. K. Singh",
            primary_image_url:
              "https://lh3.googleusercontent.com/aida-public/AB6AXuCh8eDoILqkOABABD1jYUloHvi3_vaRPwCNFXT84AWqQvqITrVLMtq9QeIMoZKK0AY0IBxciG0UyuAfJr2ck-KOBxRotBb0G34_3X8Npuk32EYjJ8lQO_M690mjzYDne9ZlxK7C08UuXkoSw19PVKKkoC9yovp1sn0piLsCZk0Nspa9BfMBJgK-HiTU00uw4dc4H1DHOxmNINsZahPfGqwyJDLwblQFo6KVvB4kwEirD3MynJaQrU_U",
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
            ],
            stats: { total: 1, passed: 1, review: 0, failed: 0 },
          };
          setEvidence(demoEvidence);
          return;
        }

        // If neither server nor local storage has this inspection:
        if (res && res.status === 403) {
          setError("Access forbidden (HTTP 403). Your officer session may belong to another user or have expired. Please re-login.");
        } else if (res && res.status === 404) {
          setError(`Inspection ${inspectionId} was not found on the server or on this device.`);
        } else {
          setError(
            res
              ? `Unable to load evidence (HTTP ${res.status}).`
              : "Unable to reach the server. Please ensure internet connectivity or check local offline storage."
          );
        }
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
