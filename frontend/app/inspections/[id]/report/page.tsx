"use client";

import React, { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Download,
  FileText,
  ShieldCheck,
  Volume2,
  FileJson,
  Loader2,
} from "lucide-react";
import { API_BASE } from "@/app/utils/apiConfig";
import { db } from "@/app/db/dexie";

interface ReportPageProps {
  params: Promise<{ id: string }>;
}

interface ReportMetadata {
  id: string;
  inspection_id: string;
  format: "pdf" | "editable";
  storage_url: string;
  download_url: string;
  generated_at: string;
}

interface EvidenceItem {
  field_label?: string;
  field_type?: string;
  parsed_value?: string;
  raw_text?: string;
  verdict: "pass" | "fail" | "review" | string;
}

interface EvidenceData {
  inspection_id: string;
  product_name: string;
  commodity_category: string;
  overall_status: string;
  rule_pack_version: string;
  officer_name: string;
  items: EvidenceItem[];
  stats?: {
    total: number;
    passed: number;
    review: number;
    failed: number;
  };
}

export default function InspectionReportPage({ params }: ReportPageProps) {
  const resolvedParams = use(params);
  const inspectionId = resolvedParams.id;
  const router = useRouter();

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [evidenceData, setEvidenceData] = useState<EvidenceData | null>(null);
  const [reports, setReports] = useState<ReportMetadata[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [isNarrating, setIsNarrating] = useState<boolean>(false);

  useEffect(() => {
    async function loadReportData() {
      setIsLoading(true);
      setError(null);

      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("access_token") || localStorage.getItem("token")
          : null;

      try {
        // 1. Fetch evidence data
        let evData = null;
        try {
          const evRes = await fetch(`${API_BASE}/inspections/${inspectionId}/evidence`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          if (evRes.ok) {
            evData = await evRes.json();
            setEvidenceData(evData);
          }
        } catch {
          // Fall back to offline local storage
        }

        // Offline fallback for evidence
        if (!evData) {
          let local = await db.inspections.get(inspectionId);
          if (!local) {
            local = await db.inspections.where("backendId").equals(inspectionId).first();
          }
          if (local) {
            evData = {
              inspection_id: local.backendId || local.id,
              product_name: `Inspected ${local.commodityCategory.replace(/_/g, " ").toUpperCase()}`,
              commodity_category: local.commodityCategory,
              overall_status: "needs_review",
              rule_pack_version: "2026.02.01",
              officer_name: "Legal Metrology Officer",
              items: [],
              stats: { total: 0, passed: 0, review: 0, failed: 0 },
            };
            setEvidenceData(evData);
          }
        }

        // 2. Fetch existing generated reports list
        try {
          const repRes = await fetch(`${API_BASE}/inspections/${inspectionId}/reports`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          if (repRes.ok) {
            const repList = await repRes.json();
            setReports(repList);
          }
        } catch {
          // Ignore fetch error in offline mode
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load report data";
        setError(msg);
      } finally {
        setIsLoading(false);
      }
    }

    loadReportData();
  }, [inspectionId]);

  // Generate or download PDF report
  const handleGeneratePdf = async () => {
    setIsGenerating(true);
    setToastMsg(null);
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("access_token") || localStorage.getItem("token")
        : null;

    try {
      const res = await fetch(`${API_BASE}/inspections/${inspectionId}/report?format=pdf`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      if (!res.ok) {
        throw new Error(`Report generation failed (HTTP ${res.status})`);
      }

      const reportMeta: ReportMetadata = await res.json();
      setReports((prev) => [reportMeta, ...prev]);

      // Download file directly
      const fileUrl = `${API_BASE}/inspections/${inspectionId}/reports/${reportMeta.id}/file`;
      const fileRes = await fetch(fileUrl, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (fileRes.ok) {
        const blob = await fileRes.blob();
        const downloadLink = document.createElement("a");
        downloadLink.href = window.URL.createObjectURL(blob);
        downloadLink.download = `NiyamDrishti_Report_${inspectionId.slice(0, 8)}.pdf`;
        document.body.appendChild(downloadLink);
        downloadLink.click();
        downloadLink.remove();
        setToastMsg("PDF Report downloaded successfully.");
      } else {
        window.open(reportMeta.storage_url, "_blank");
      }
    } catch {
      // Offline fallback: generate structured JSON or text report
      setToastMsg("Server unavailable. Exporting offline compliance dossier...");
      const offlineDoc = {
        title: "NiyamDrishti Compliance Dossier",
        inspection_id: inspectionId,
        evidence: evidenceData,
        exported_at: new Date().toISOString(),
        notice: "Generated in offline mode. Full PDF will synchronize on cloud reconnection.",
      };
      const blob = new Blob([JSON.stringify(offlineDoc, null, 2)], { type: "application/json" });
      const downloadLink = document.createElement("a");
      downloadLink.href = window.URL.createObjectURL(blob);
      downloadLink.download = `Inspection_${inspectionId.slice(0, 8)}_Offline.json`;
      document.body.appendChild(downloadLink);
      downloadLink.click();
      downloadLink.remove();
    } finally {
      setIsGenerating(false);
      setTimeout(() => setToastMsg(null), 4000);
    }
  };

  // Generate or download editable JSON export
  const handleGenerateEditable = async () => {
    setIsGenerating(true);
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("access_token") || localStorage.getItem("token")
        : null;

    try {
      const res = await fetch(`${API_BASE}/inspections/${inspectionId}/report?format=editable`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      if (!res.ok) throw new Error("Editable export generation failed");

      const reportMeta: ReportMetadata = await res.json();
      const fileUrl = `${API_BASE}/inspections/${inspectionId}/reports/${reportMeta.id}/file`;
      const fileRes = await fetch(fileUrl, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (fileRes.ok) {
        const blob = await fileRes.blob();
        const downloadLink = document.createElement("a");
        downloadLink.href = window.URL.createObjectURL(blob);
        downloadLink.download = `Inspection_${inspectionId.slice(0, 8)}_Editable.json`;
        document.body.appendChild(downloadLink);
        downloadLink.click();
        downloadLink.remove();
        setToastMsg("Editable JSON export downloaded.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Export failed";
      setToastMsg("Error generating editable export: " + msg);
    } finally {
      setIsGenerating(false);
      setTimeout(() => setToastMsg(null), 3500);
    }
  };

  // Voice narration readout via Bhashini
  const handleVoiceNarration = async () => {
    if (!evidenceData) return;
    setIsNarrating(true);
    setToastMsg("Preparing voice briefing...");

    const summaryText = `Inspection report for ${evidenceData.product_name}. Category: ${evidenceData.commodity_category}. Overall status is ${evidenceData.overall_status.replace(/_/g, " ")}. Total declarations checked: ${evidenceData.items?.length || 0}.`;

    try {
      if ("speechSynthesis" in window) {
        const utterance = new SpeechSynthesisUtterance(summaryText);
        utterance.rate = 0.95;
        utterance.onend = () => setIsNarrating(false);
        window.speechSynthesis.speak(utterance);
        setToastMsg("Playing speech briefing...");
      } else {
        setToastMsg("Text-to-speech not supported on this browser.");
        setIsNarrating(false);
      }
    } catch {
      setIsNarrating(false);
    }
    setTimeout(() => setToastMsg(null), 3500);
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#F9F7F2] text-[#1A1C1E]">
        <Loader2 className="w-8 h-8 animate-spin text-[#333E50] mb-3" />
        <p className="text-sm font-mono text-[#75777D]">Loading Inspection Report Center...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-full max-w-2xl mx-auto min-h-screen bg-[#F9F7F2] text-[#1A1C1E] shadow-xl">
      {/* Top Header */}
      <header className="sticky top-0 z-40 bg-[#F9F7F2]/95 backdrop-blur-md border-b border-[#D1CDC2] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => router.back()}
            className="p-1.5 rounded-full hover:bg-black/5 active:scale-95 text-[#333E50]"
            aria-label="Go Back"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="font-bold text-base text-[#1A1C1E] leading-tight">Report Center</h1>
            <p className="text-[10px] font-mono text-[#75777D]">LEGAL METROLOGY (PC) RULES, 2011</p>
          </div>
        </div>

        <button
          onClick={handleVoiceNarration}
          disabled={isNarrating}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#EAE7DC] text-[#333E50] hover:bg-[#DDD9CD] rounded-md text-xs font-mono font-medium active:scale-95 transition-all shadow-sm"
        >
          <Volume2 className="w-3.5 h-3.5 text-[#333E50]" />
          <span>{isNarrating ? "Playing..." : "Briefing"}</span>
        </button>
      </header>

      {/* Toast */}
      {toastMsg && (
        <div className="fixed top-14 inset-x-4 max-w-sm mx-auto z-50 bg-[#333E50] text-white px-4 py-2.5 rounded-lg shadow-xl text-xs font-mono flex items-center justify-between border border-white/20 animate-in fade-in slide-in-from-top-2">
          <span>{toastMsg}</span>
          <button onClick={() => setToastMsg(null)} className="text-white/60 ml-2">✕</button>
        </div>
      )}

      <main className="p-4 flex-1 flex flex-col gap-4 pb-20">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-3.5 py-2.5 rounded-lg text-xs font-mono">
            {error}
          </div>
        )}

        {/* Official Statutory Dossier Header Card */}
        <div className="bg-white rounded-lg border border-[#D1CDC2] p-4 shadow-sm">
          <div className="flex items-start justify-between border-b border-[#EAE7DC] pb-3 mb-3">
            <div>
              <span className="text-[10px] font-mono font-bold tracking-wider text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                OFFICIAL INSPECTION DOSSIER
              </span>
              <h2 className="text-lg font-bold text-[#1A1C1E] mt-1.5">
                {evidenceData?.product_name || "Packaged Commodity Inspection"}
              </h2>
              <p className="text-xs text-[#75777D] capitalize">
                Category: {evidenceData?.commodity_category?.replace(/_/g, " ") || "General"}
              </p>
            </div>

            <div className="flex flex-col items-end text-right font-mono text-[11px]">
              <span className="text-gray-500">ID: {inspectionId.slice(0, 10)}</span>
              <span className="text-emerald-700 font-bold mt-1">
                {evidenceData?.overall_status === "compliant"
                  ? "COMPLIANT"
                  : evidenceData?.overall_status === "violations_found"
                  ? "VIOLATIONS DETECTED"
                  : "NEEDS OFFICER REVIEW"}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="bg-[#F9F7F2] p-2.5 rounded border border-[#EAE7DC]">
              <span className="text-[10px] text-[#75777D] block">INSPECTION OFFICER</span>
              <span className="font-semibold text-[#1A1C1E] mt-0.5 block">
                {evidenceData?.officer_name || "Legal Metrology Inspector"}
              </span>
            </div>
            <div className="bg-[#F9F7F2] p-2.5 rounded border border-[#EAE7DC]">
              <span className="text-[10px] text-[#75777D] block">RULE PACK VERSION</span>
              <span className="font-semibold text-[#1A1C1E] mt-0.5 block">
                v{evidenceData?.rule_pack_version || "2026.02.01"}
              </span>
            </div>
          </div>
        </div>

        {/* Declarations Findings Summary */}
        <div className="bg-white rounded-lg border border-[#D1CDC2] p-4 shadow-sm">
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-[#4A5568] mb-2.5">
            Statutory Declarations Verified
          </h3>

          {evidenceData?.items?.length ? (
            <div className="flex flex-col divide-y divide-gray-100 text-xs">
              {evidenceData.items.map((item, idx: number) => (
                <div key={idx} className="py-2 flex items-center justify-between">
                  <div>
                    <span className="font-mono font-bold text-gray-800 uppercase block">
                      {item.field_label || item.field_type}
                    </span>
                    <span className="font-mono text-[11px] text-gray-500">
                      {item.parsed_value || item.raw_text || "Extracted"}
                    </span>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                      item.verdict === "pass"
                        ? "bg-emerald-100 text-emerald-800"
                        : item.verdict === "fail"
                        ? "bg-red-100 text-red-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {item.verdict.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-500 font-mono italic">
              Declarations extracted and archived in report dossier.
            </p>
          )}
        </div>

        {/* Download Action Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* PDF Official Report */}
          <div className="bg-white rounded-lg border border-[#D1CDC2] p-3.5 flex flex-col justify-between shadow-sm">
            <div>
              <div className="w-8 h-8 rounded bg-red-100 text-red-700 flex items-center justify-center mb-2">
                <FileText className="w-4 h-4" />
              </div>
              <h4 className="font-bold text-sm text-[#1A1C1E]">Statutory PDF Report</h4>
              <p className="text-[11px] text-[#75777D] mt-0.5">
                Official court-ready inspection certificate with pixel bounding-box evidence.
              </p>
            </div>
            <button
              onClick={handleGeneratePdf}
              disabled={isGenerating}
              className="mt-3 w-full py-2 bg-[#333E50] hover:bg-[#27303E] text-white rounded font-mono text-xs font-bold flex items-center justify-center gap-1.5 active:scale-95 transition-all"
            >
              {isGenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              <span>Download PDF</span>
            </button>
          </div>

          {/* Editable JSON Dataset */}
          <div className="bg-white rounded-lg border border-[#D1CDC2] p-3.5 flex flex-col justify-between shadow-sm">
            <div>
              <div className="w-8 h-8 rounded bg-blue-100 text-blue-700 flex items-center justify-center mb-2">
                <FileJson className="w-4 h-4" />
              </div>
              <h4 className="font-bold text-sm text-[#1A1C1E]">Editable JSON Export</h4>
              <p className="text-[11px] text-[#75777D] mt-0.5">
                Machine-readable structured dataset containing OCR tokens and audit logs.
              </p>
            </div>
            <button
              onClick={handleGenerateEditable}
              disabled={isGenerating}
              className="mt-3 w-full py-2 bg-white border border-[#D1CDC2] hover:bg-gray-50 text-[#333E50] rounded font-mono text-xs font-bold flex items-center justify-center gap-1.5 active:scale-95 transition-all"
            >
              {isGenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              <span>Export JSON</span>
            </button>
          </div>
        </div>

        {/* Generated Reports History */}
        {reports.length > 0 && (
          <div className="bg-white rounded-lg border border-[#D1CDC2] p-3.5 text-xs shadow-sm">
            <h4 className="font-bold font-mono uppercase tracking-wider text-gray-700 mb-2">
              Generated Reports ({reports.length})
            </h4>
            <div className="flex flex-col divide-y divide-gray-100">
              {reports.map((rep) => (
                <div key={rep.id} className="py-1.5 flex items-center justify-between text-[11px] font-mono">
                  <span className="text-gray-700 font-semibold">{rep.format.toUpperCase()} Dossier</span>
                  <span className="text-gray-400">{new Date(rep.generated_at).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Section 63 BSA Digital Evidence Certificate Notice */}
        <div className="bg-[#EAE7DC]/60 rounded-lg border border-[#D1CDC2] p-3.5 text-xs text-[#333E50]">
          <div className="flex items-center gap-2 font-mono font-bold mb-1">
            <ShieldCheck className="w-4 h-4 text-emerald-700" />
            <span>Section 63 Bharatiya Sakshya Adhiniyam (BSA) 2023</span>
          </div>
          <p className="text-[11px] text-gray-600 leading-relaxed font-mono">
            Every inspection report generated by NiyamDrishti embeds cryptographic SHA-256 capture hashes, calibrated optical scale logs, and immutable audit timestamps complying with statutory electronic evidence requirements.
          </p>
        </div>

        {/* Statutory Disclaimer per RPT-02 */}
        <div className="p-3 bg-white/60 rounded border border-[#D1CDC2] text-[10px] text-gray-500 font-mono leading-tight">
          <span className="font-bold block text-gray-700 mb-0.5">STATUTORY NOTICE & LEGAL DISCLAIMER:</span>
          This report is a technical decision-support document generated under the Legal Metrology (Packaged Commodities) Rules, 2011. The findings contained herein reflect optical analysis and rule evaluation of photographed packaging panels and do not constitute a final judicial ruling.
        </div>
      </main>
    </div>
  );
}
