"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ArrowLeft, Loader2, ScanText, WifiOff } from "lucide-react";
import { db } from "@/app/db/dexie";
import EvidenceViewer from "@/app/components/evidence/EvidenceViewer";
import type { InspectionEvidence } from "@/app/types/evidence";
import {
  buildOfflineEvidence,
  matchOfflineSample,
  type OcrPanel,
  recogniseOfflineImage,
} from "@/app/services/offlineVerifiedService";

function saveOfflineReport(evidence: InspectionEvidence) {
  const compactReport = {
    inspection_id: evidence.inspection_id,
    product_name: evidence.product_name,
    commodity_category: evidence.commodity_category,
    rule_pack_version: evidence.rule_pack_version,
    generated_at: new Date().toISOString(),
    items: evidence.items.map(({ field_label, parsed_value, raw_text, verdict, review_reason, violations }) => ({ field_label, parsed_value, raw_text, verdict, review_reason, violations })),
  };
  sessionStorage.setItem("offline_verified_report", JSON.stringify(compactReport));
}

export default function OfflineVerifiedCheck({ inspectionId }: { inspectionId: string }) {
  const router = useRouter();
  const [progress, setProgress] = useState(0);
  const [evidence, setEvidence] = useState<InspectionEvidence | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    async function run() {
      try {
        const images = await db.inspectionImages.where("inspectionId").equals(inspectionId).toArray();
        const orderedImages = [...images].sort((a, b) => (a.imageRole === "front_pdp" ? -1 : b.imageRole === "front_pdp" ? 1 : 0));
        if (!orderedImages[0]) throw new Error("No local photo was found for this inspection.");
        const panels: OcrPanel[] = [];
        for (let index = 0; index < orderedImages.length; index += 1) {
          const image = orderedImages[index];
          const result = await recogniseOfflineImage(image.dataUrl, (value) => setProgress(Math.round(((index + value / 100) / orderedImages.length) * 100)));
          panels.push({
            id: image.id,
            label: image.imageRole === "front_pdp" ? "Front PDP" : image.imageRole.replace(/_/g, " "),
            imageUrl: image.dataUrl,
            lines: result.lines,
            imageSize: result.imageSize,
          });
        }
        if (!alive) return;
        const match = matchOfflineSample(panels.flatMap((panel) => panel.lines));
        if (!match) {
          setError("Local OCR could not read a reliable product identifier. Retake the front and back panels with the label flat, bright, and in focus.");
          return;
        }
        const nextEvidence = buildOfflineEvidence(match, panels, inspectionId);
        saveOfflineReport(nextEvidence);
        setEvidence(nextEvidence);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Offline text recognition could not complete.");
      }
    }
    run();
    return () => { alive = false; };
  }, [inspectionId]);

  if (evidence) {
    return (
      <>
        <div className="sticky top-0 z-50 bg-[#e8eef6] border-b border-[#9ba9be] px-4 py-2.5 text-[#1a1c1e]">
          <div className="mx-auto max-w-4xl flex gap-2.5 items-start">
            <WifiOff className="w-4 h-4 mt-0.5 shrink-0 text-[#333e50]" />
            <div>
              <p className="font-mono text-xs font-bold tracking-wide">OFFLINE · SAVED SAMPLE CHECK</p>
              <p className="text-xs mt-0.5">Boxes mark current local text; Review items still need officer confirmation.</p>
            </div>
          </div>
        </div>
        <EvidenceViewer
          evidence={evidence}
          onReviewQueueClick={() => router.push(`/inspections/${inspectionId}/review`)}
          onGenerateReportClick={() => router.push("/offline-verified/report")}
        />
      </>
    );
  }

  return (
    <main className="min-h-screen bg-[#f9f9fc] flex items-center justify-center p-5 text-[#1a1c1e]">
      <section className="w-full max-w-md border border-[#c5c6cd] bg-white rounded-md p-6 shadow-sm">
        {error ? <AlertTriangle className="w-10 h-10 text-amber-700 mb-4" /> : <ScanText className="w-10 h-10 text-[#333e50] mb-4" />}
        <p className="font-mono text-xs tracking-wider text-[#545f72] mb-2">OFFLINE LOCAL OCR</p>
        <h1 className="text-xl font-semibold">{error ? "A clearer capture is needed" : "Reading this local capture"}</h1>
        <p className="text-sm text-[#44474c] mt-2">{error || `Packaged OCR is running on this device (${progress}%). No photo or text is being sent to a server.`}</p>
        {!error && <Loader2 className="w-5 h-5 animate-spin text-[#333e50] mt-5" />}
        {error && <button onClick={() => router.push("/")} className="mt-4 inline-flex items-center gap-2 bg-[#333e50] text-white px-4 py-2 rounded text-sm"><ArrowLeft className="w-4 h-4" /> Back to capture</button>}
      </section>
    </main>
  );
}
