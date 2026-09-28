"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import EvidenceViewer from "@/app/components/evidence/EvidenceViewer";
import LocalProvisionalEvidenceViewer from "@/app/components/evidence/LocalProvisionalEvidenceViewer";
import { InspectionEvidence } from "@/app/types/evidence";
import { db, getLocalEvidence, OfflineImage, OfflineInspection, OfflineLocalEvidence } from "@/app/db/dexie";
import { useOfflineQueue } from "@/app/hooks/useOfflineQueue";
import { ArrowLeft, Loader2 } from "lucide-react";
import { API_BASE } from "@/app/utils/apiConfig";

export default function EvidencePage() {
  return (
    <Suspense fallback={null}>
      <EvidencePageContent />
    </Suspense>
  );
}

function EvidencePageContent() {
  const searchParams = useSearchParams();
  const inspectionId = searchParams.get("id") || "";
  const router = useRouter();

  const [evidence, setEvidence] = useState<InspectionEvidence | null>(null);
  const [localInspection, setLocalInspection] = useState<OfflineInspection | null>(null);
  const [localEvidence, setLocalEvidence] = useState<OfflineLocalEvidence | null>(null);
  const [localImages, setLocalImages] = useState<OfflineImage[]>([]);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const { syncInspectionNow, isSyncing } = useOfflineQueue();

  const handleBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }
    router.replace("/history");
  };

  useEffect(() => {
    async function loadEvidence() {
      if (!inspectionId) {
        setError("No inspection was selected. Return to History and open an inspection.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      setLocalInspection(null);
      setLocalEvidence(null);
      setLocalImages([]);
      setSyncError(null);

      try {
        // A direct local ID represents an unsynced offline inspection. Prefer
        // durable local evidence and make no server request in that state.
        const directLocalInspection = await db.inspections.get(inspectionId);
        if (directLocalInspection && directLocalInspection.status !== "synced") {
          const savedLocalEvidence = await getLocalEvidence(inspectionId);
          if (savedLocalEvidence) {
            setLocalInspection(directLocalInspection);
            setLocalEvidence(savedLocalEvidence);
            setLocalImages(await db.inspectionImages.where("inspectionId").equals(inspectionId).toArray());
            return;
          }
        }

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

  const handleLocalSync = async (localInspectionId: string) => {
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      setSyncError("Connect to the Internet before choosing Sync Now.");
      return;
    }
    setSyncError(null);
    const result = await syncInspectionNow(localInspectionId);
    if (result.success && result.backendId) {
      router.replace(`/inspections/evidence?id=${encodeURIComponent(result.backendId)}`);
      return;
    }
    setSyncError(result.error || "Sync could not finish. Your local evidence remains safely stored on this device.");
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#f9f9fc] text-[#1a1c1e]">
        <Loader2 className="w-8 h-8 animate-spin text-[#333e50] mb-3" />
        <p className="text-sm font-mono text-[#75777d]">Loading inspection evidence...</p>
      </div>
    );
  }

  if (localInspection && localEvidence) {
    return (
      <LocalProvisionalEvidenceViewer
        inspectionId={localInspection.id}
        capturedAt={localInspection.createdAt}
        images={localImages}
        evidence={localEvidence}
        isSyncing={isSyncing}
        syncError={syncError}
        onSyncNow={() => handleLocalSync(localInspection.id)}
        onBack={handleBack}
      />
    );
  }

  if (error || !evidence) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#f9f9fc] text-[#1a1c1e] p-6">
        <p className="text-sm font-mono text-red-600 mb-4">{error || "Evidence record not found"}</p>
        <button
          type="button"
          onClick={handleBack}
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
      onBack={handleBack}
      onReviewQueueClick={() => router.push(`/inspections/review?id=${encodeURIComponent(inspectionId)}`)}
      onGenerateReportClick={() => router.push(`/inspections/report?id=${encodeURIComponent(inspectionId)}`)}
    />
  );
}
