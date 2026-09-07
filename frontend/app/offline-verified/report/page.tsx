"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Download, FileText, Printer } from "lucide-react";

interface OfflineReport {
  inspection_id: string;
  product_name: string;
  commodity_category: string;
  rule_pack_version: string;
  generated_at: string;
  items: Array<{ field_label: string; parsed_value?: string | null; raw_text?: string | null; verdict: string; review_reason?: string | null }>;
}

export default function OfflineReportPage() {
  const [report, setReport] = useState<OfflineReport | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const stored = sessionStorage.getItem("offline_verified_report");
      if (stored) setReport(JSON.parse(stored) as OfflineReport);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  if (!report) return <main className="min-h-screen bg-[#f9f9fc] p-6 text-[#44474c]">No offline report is available for this session.</main>;

  return (
    <main className="min-h-screen bg-[#f0ede5] p-4 sm:p-8 text-[#1a1c1e]">
      <article className="max-w-3xl mx-auto bg-white border border-[#c5c6cd] shadow-sm p-6 sm:p-10 print:border-0 print:shadow-none">
        <div className="flex justify-between gap-4 border-b border-[#d1cdc2] pb-5">
          <div><p className="font-mono text-xs tracking-wider text-[#566155]">NIYAMDRISHTI · OFFLINE INSPECTION REPORT</p><h1 className="mt-2 text-2xl font-bold">{report.product_name}</h1><p className="text-sm capitalize text-[#545f72]">{report.commodity_category.replace(/_/g, " ")}</p></div>
          <FileText className="w-9 h-9 text-[#333e50] shrink-0" />
        </div>
        <dl className="grid grid-cols-2 gap-4 py-5 text-xs border-b border-[#d1cdc2]"><div><dt className="font-mono text-[#75777d]">INSPECTION ID</dt><dd className="font-mono mt-1">{report.inspection_id}</dd></div><div><dt className="font-mono text-[#75777d]">RULE PACK</dt><dd className="font-mono mt-1">v{report.rule_pack_version}</dd></div></dl>
        <section className="py-5"><h2 className="font-semibold">Declaration register</h2><div className="mt-3 divide-y divide-[#e2e2e5] border-y border-[#e2e2e5]">{report.items.map((item) => <div key={item.field_label} className="py-3"><div className="flex justify-between gap-3"><strong className="text-sm">{item.field_label}</strong><span className={`font-mono text-xs ${item.verdict === "pass" ? "text-emerald-700" : item.verdict === "fail" ? "text-red-700" : "text-amber-800"}`}>{item.verdict.toUpperCase()}</span></div><p className="font-mono text-sm mt-1">{item.parsed_value || "—"}</p>{item.review_reason && <p className="text-xs text-amber-800 mt-1">{item.review_reason}</p>}</div>)}</div></section>
        <p className="text-xs text-[#545f72] border-t border-[#d1cdc2] pt-4">Offline saved-sample output. Confirm Review items before enforcement action.</p>
        <div className="mt-6 flex gap-3 print:hidden"><button onClick={() => window.print()} className="inline-flex items-center gap-2 bg-[#333e50] text-white px-4 py-2 rounded text-sm"><Printer className="w-4 h-4" /> Save / Print PDF</button><Link href="/" className="inline-flex items-center gap-2 border border-[#75777d] px-4 py-2 rounded text-sm"><Download className="w-4 h-4" /> New capture</Link></div>
      </article>
    </main>
  );
}
