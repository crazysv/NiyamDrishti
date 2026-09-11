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
          setError(
            "This inspection is saved on this device and has not been analysed yet. Use Sync Now from History after a connection is available."
          );
          return;
        }

        // If neither server nor local storage has this inspection:
        if (res && res.status === 409) {
          const payload = await res.json().catch(() => null);
          setError(payload?.detail || "Evidence is still uploading. Return to History and retry the upload.");
        } else if (res && res.status === 403) {
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
