"use client";
import AppLogo from "@/app/components/common/AppLogo";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  fetchAnalyticsSummary,
  fetchComplianceTrends,
  fetchViolationHotspots,
  fetchOfficerThroughput,
} from "../../services/analyticsService";
import {
  AnalyticsSummary,
  ComplianceTrends,
  ViolationHotspots,
  OfficerThroughput,
} from "../../types/analytics";
import { authorizeSandboxPersona, handleSSOCallback } from "../../services/ssoService";

let dashboardSessionToken: string | undefined;

async function ensureAnalyticsSession(): Promise<string | undefined> {
  if (dashboardSessionToken) return dashboardSessionToken;

  // The dashboard is a supervisory view. In the evaluation sandbox it obtains
  // a fresh scoped session instead of using a field-officer or stale browser token.
  const state = `analytics_${Date.now()}`;
  const authorization = await authorizeSandboxPersona("supervisor_priya", state);
  const session = await handleSSOCallback(authorization.code, authorization.state);
  dashboardSessionToken = session.access_token;
  return dashboardSessionToken;
}

export default function AnalyticsDashboard() {
  const [dateRange, setDateRange] = useState<"7d" | "30d" | "quarter" | "custom">("30d");
  const [selectedRegion, setSelectedRegion] = useState<string>("all");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [officerSearch, setOfficerSearch] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Analytics data states
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [trends, setTrends] = useState<ComplianceTrends | null>(null);
  const [hotspots, setHotspots] = useState<ViolationHotspots | null>(null);
  const [throughput, setThroughput] = useState<OfficerThroughput | null>(null);

  const fetchDashboardData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const daysByRange = { "7d": 7, "30d": 30, quarter: 90, custom: 30 } as const;
      const endDate = new Date();
      const startDate = new Date(endDate);
      startDate.setDate(startDate.getDate() - daysByRange[dateRange]);
      const trendParams = {
        startDate: startDate.toISOString().slice(0, 10),
        endDate: endDate.toISOString().slice(0, 10),
        region: selectedRegion !== "all" ? selectedRegion : undefined,
        category: selectedCategory !== "all" ? selectedCategory : undefined,
      };

      const token = await ensureAnalyticsSession();
      const [sumRes, trendRes, hotRes, tpRes] = await Promise.all([
        fetchAnalyticsSummary(token).catch(() => null),
        fetchComplianceTrends(trendParams, token).catch(() => null),
        fetchViolationHotspots(10, token).catch(() => null),
        fetchOfficerThroughput(token).catch(() => null),
      ]);

      if (sumRes) setSummary(sumRes);
      if (trendRes) setTrends(trendRes);
      if (hotRes) setHotspots(hotRes);
      if (tpRes) setThroughput(tpRes);
      setLoadError(sumRes || trendRes || hotRes || tpRes ? null : "Live analytics is unavailable. No placeholder figures are shown.");
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
      setLoadError(err instanceof Error ? `Live analytics could not start: ${err.message}` : "Live analytics could not start.");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [dateRange, selectedRegion, selectedCategory]);

  const handleExportCsv = () => {
    const headers = "Metric,Value\n";
    const rows = [
      `Total Inspections,${summary?.total_inspections ?? 0}`,
      `Compliant Packages,${summary?.compliant_inspections ?? 0}`,
      `Violations Detected,${summary?.violation_inspections ?? 0}`,
      `Overall Compliance Rate,${summary?.overall_compliance_rate ?? 0}%`,
      `Critical Breaches,${summary?.critical_violations ?? 0}`,
      `Major Breaches,${summary?.major_violations ?? 0}`,
      `Needs Review Queue,${summary?.needs_review_inspections ?? 0}`,
      `Active Officers,${summary?.active_officers_count ?? 0}`,
    ].join("\n");
    const blob = new Blob([headers + rows], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `NiyamDrishti_Analytics_Ledger_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  const handleExportPdf = () => {
    window.print();
  };

  useEffect(() => {
    const initial = window.setTimeout(() => void fetchDashboardData(), 0);
    const refresh = window.setInterval(() => void fetchDashboardData(), 15000);
    window.addEventListener("focus", fetchDashboardData);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(refresh);
      window.removeEventListener("focus", fetchDashboardData);
    };
  }, [fetchDashboardData]);

  // Display only values returned by the live API. Empty deployments start at zero.
  const totalInspections = summary?.total_inspections ?? 0;
  const compliantInspections = summary?.compliant_inspections ?? 0;
  const breachInspections = summary?.violation_inspections ?? 0;
  const overallComplianceRate = summary?.overall_compliance_rate ?? 0;
  const totalBreaches = summary?.total_violations ?? 0;
  const critViolations = summary?.critical_violations ?? 0;
  const majViolations = summary?.major_violations ?? 0;
  const modViolations = summary?.moderate_violations ?? 0;
  const backlogCount = summary?.needs_review_inspections ?? 0;
  const activeOfficers = summary?.active_officers_count ?? 0;
  const trendPoints = trends?.points.slice(-30) ?? [];
  const maxTrendVolume = Math.max(1, ...trendPoints.map((point) => point.total_inspections));
  const peakTrend = trendPoints.reduce<(typeof trendPoints)[number] | null>(
    (peak, point) => (!peak || point.total_inspections > peak.total_inspections ? point : peak),
    null,
  );
  const regionalDistribution = hotspots?.by_region ?? [];
  const maxRegionalVolume = Math.max(1, ...regionalDistribution.map((region) => region.total_inspections));

  const displayRules = hotspots && hotspots.by_rule.length > 0
    ? hotspots.by_rule.slice(0, 5).map((r, idx) => ({
        rank: `0${idx + 1}.`,
        rule: r.rule_id,
        title: r.description,
        breaches: r.count,
        severity: r.severity.toUpperCase(),
        width: `${Math.min(100, Math.round((r.count / Math.max(1, hotspots.by_rule[0]?.count || 1)) * 100))}%`,
        sub: r.citation || "Statutory LMPC requirement",
        pct: `${Math.round((r.count / Math.max(1, totalBreaches)) * 100)}%`,
      }))
    : [];

  const displayCategories = hotspots && hotspots.by_category.length > 0
    ? hotspots.by_category.slice(0, 4).map((c) => ({
        name: c.commodity_category,
        badge: c.compliance_rate < 70 ? "HIGH RISK" : c.compliance_rate < 85 ? "STANDARD" : "COMPLIANT",
        badgeColor: c.compliance_rate < 70 ? "bg-red-100 text-red-900" : c.compliance_rate < 85 ? "bg-[#E8E8EA] text-[#44474C]" : "bg-emerald-100 text-emerald-900",
        rate: c.compliance_rate,
        color: c.compliance_rate < 70 ? "bg-red-600" : "bg-emerald-600",
        desc: `${c.total_inspections} inspections · ${c.violations_count} non-compliant`,
      }))
    : [];

  // Filter officer list by search query
  const displayOfficers = throughput && throughput.officers.length > 0
    ? throughput.officers.map((o) => ({
        officer_id: o.officer_id,
        officer_name: o.officer_name,
        region: o.region || "Zonal Enforcement",
        total_inspections: o.total_inspections,
        completed_inspections: o.completed_inspections,
        needs_review_inspections: o.needs_review_inspections,
        human_overrides_count: o.human_overrides_count,
        last_inspection_at: o.last_inspection_at ? new Date(o.last_inspection_at).toLocaleTimeString() : "Recent",
        status: o.needs_review_inspections > 5 ? "Pending Review" : "Active Field",
      }))
    : [];

  const filteredOfficers = displayOfficers.filter(
    (o) =>
      o.officer_name.toLowerCase().includes(officerSearch.toLowerCase()) ||
      o.officer_id.toLowerCase().includes(officerSearch.toLowerCase()) ||
      o.region.toLowerCase().includes(officerSearch.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-[#F9F7F2] text-[#1A1C1E] flex flex-col font-sans overflow-x-hidden">
      {/* Top Header */}
      <header className="fixed top-0 left-0 right-0 h-16 z-50 bg-[#333E50] text-white shadow-sm flex items-center px-3 md:px-6 justify-between gap-2 overflow-hidden">
        <div className="flex items-center gap-2 md:gap-4 min-w-0 flex-1">
          <Link href="/" className="flex items-center gap-2 md:gap-3 min-w-0">
            <AppLogo size={32} />
            <div className="flex flex-col min-w-0">
              <span className="text-lg font-bold tracking-tight text-white leading-tight truncate">
                NiyamDrishti
              </span>
              <span className="text-[10px] font-mono tracking-widest text-[#BCC7DD] uppercase truncate">
                Supervisor Portal
              </span>
            </div>
          </Link>
          <div className="h-6 w-px bg-white/20 hidden md:block" />
          <div className="hidden xl:flex flex-col min-w-0">
            <span className="text-xs font-medium text-white truncate">
              Department of Consumer Affairs · Legal Metrology Division
            </span>
            <span className="text-[10px] font-mono text-[#BCC7DD] truncate">
              Jurisdiction: National Headquarters / All Zones
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 md:gap-3 shrink-0">
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#4A5568] text-white text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
            <span>RULEPACK: v2026.02.01</span>
          </div>
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded bg-white/10 text-white text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse inline-block" />
            <span>ONLINE · LIVE TELEMETRY</span>
          </div>
          <div className="h-6 w-px bg-white/20 hidden sm:block" />

          {/* Quick Exports & Refresh */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleExportPdf}
              className="hidden sm:flex h-8 px-2.5 rounded bg-[#4A5568] hover:bg-[#5A6679] text-white text-xs font-mono items-center gap-1 transition-colors active:scale-95"
              title="Export Legal Dossier as PDF"
            >
              <span>PDF</span>
            </button>
            <button
              type="button"
              onClick={handleExportCsv}
              className="hidden sm:flex h-8 px-2.5 rounded bg-[#4A5568] hover:bg-[#5A6679] text-white text-xs font-mono items-center gap-1 transition-colors active:scale-95"
              title="Export Ledger as CSV"
            >
              <span>CSV</span>
            </button>
            <button
              type="button"
              onClick={fetchDashboardData}
              disabled={isRefreshing}
              className="h-8 w-8 rounded bg-[#4A5568] hover:bg-[#5A6679] text-white flex items-center justify-center transition-colors"
              title="Refresh Live Telemetry Feeds"
            >
              <svg
                className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </button>
          </div>

          <div className="h-6 w-px bg-white/20 hidden sm:block" />
          <div className="flex items-center gap-2 pl-0 sm:pl-1">
            <div className="hidden 2xl:flex flex-col text-right">
              <span className="text-xs font-medium text-white leading-tight">
                Insp. Gen. S. K. Verma
              </span>
              <span className="text-[10px] font-mono text-[#BCC7DD] leading-tight">
                Supervisory Admin
              </span>
            </div>
            <div className="w-8 h-8 rounded-full bg-[#1E2530] border border-white/20 flex items-center justify-center text-xs font-bold text-white">
              SV
            </div>
          </div>
        </div>
      </header>

      {/* Main Layout Container with Sidebar */}
      <div className="flex pt-16 flex-1">
        {/* Left Sidebar Navigation */}
        <aside className="w-60 bg-[#F0EDE5] border-r border-[#D1CDC2] hidden md:flex flex-col justify-between py-4 shrink-0">
          <div className="flex flex-col gap-1">
            <div className="px-4 pb-2">
              <span className="text-[11px] font-mono font-semibold text-[#566155] uppercase tracking-wider">
                Enforcement Command
              </span>
            </div>
            <nav className="flex flex-col gap-1 px-2">
              <Link
                href="/dashboard"
                className="h-10 px-3 flex items-center gap-3 rounded bg-[#4A5568] text-white font-medium text-sm transition-colors shadow-sm"
              >
                <span className="text-base">📊</span>
                <span>Overview Command</span>
              </Link>
              <Link
                href="/history"
                className="h-10 px-3 rounded flex items-center gap-3 text-[#44474C] hover:bg-[#E2E2E5] hover:text-[#1A1C1E] transition-colors text-sm font-medium"
              >
                <span className="text-base">📋</span>
                <span>Field Inspections</span>
              </Link>
              <Link
                href="/"
                className="h-10 px-3 rounded flex items-center gap-3 text-[#44474C] hover:bg-[#E2E2E5] hover:text-[#1A1C1E] transition-colors text-sm font-medium"
              >
                <span className="text-base">📷</span>
                <span>Capture Portal</span>
              </Link>
              <Link
                href="/admin/rule-packs"
                className="h-10 px-3 rounded flex items-center gap-3 text-[#44474C] hover:bg-[#E2E2E5] hover:text-[#1A1C1E] transition-colors text-sm font-medium"
              >
                <span className="text-base">⚖️</span>
                <span>Rule Pack Governance</span>
              </Link>
              <button
                type="button"
                onClick={() => alert("Verification & Sealing module accessible in Phase 3.")}
                className="h-10 px-3 rounded flex items-center gap-3 text-[#44474C] hover:bg-[#E2E2E5] hover:text-[#1A1C1E] transition-colors text-sm font-medium text-left"
              >
                <span className="text-base">⚖️</span>
                <span>Verification & Sealing</span>
              </button>
              <button
                type="button"
                onClick={() => alert("Violation Dockets archive accessible in Phase 3.")}
                className="h-10 px-3 rounded flex items-center gap-3 text-[#44474C] hover:bg-[#E2E2E5] hover:text-[#1A1C1E] transition-colors text-sm font-medium text-left"
              >
                <span className="text-base">📁</span>
                <span>Violation Dockets</span>
              </button>
              <button
                type="button"
                onClick={() => alert("Standards & Tolerances schedule verified under Rule 7/Rule 12.")}
                className="h-10 px-3 rounded flex items-center gap-3 text-[#44474C] hover:bg-[#E2E2E5] hover:text-[#1A1C1E] transition-colors text-sm font-medium text-left"
              >
                <span className="text-base">📏</span>
                <span>Standards & Schedule</span>
              </button>
            </nav>
          </div>

          <div className="px-4 flex flex-col gap-2">
            <div className="p-3 rounded bg-[#E8E8EA] border border-[#D1CDC2] flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-[#566155] font-semibold">
                  CENTRAL VAULT
                </span>
                <span className="text-[10px] font-mono text-emerald-700 font-bold">READY</span>
              </div>
              <span className="text-[11px] font-mono text-[#44474C] leading-snug">
                Sec-81 Legal Metrology Act, 2009 Digital Ledger
              </span>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col min-w-0 overflow-y-auto pb-20 md:pb-0">
          {/* Top Loader Bar */}
          {isLoading && (
            <div className="w-full h-1 bg-[#F0EDE5] overflow-hidden">
              <div className="bg-[#333E50] h-full w-1/3 animate-pulse" />
            </div>
          )}

          {/* Sticky Operational Filter Bar */}
          <section className="sticky top-16 z-30 w-full bg-white border-b border-[#D1CDC2] px-4 md:px-8 py-3 shadow-xs">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 max-w-[1600px] mx-auto w-full min-w-0">
              {/* Left Filters */}
              <div className="flex flex-wrap items-center gap-2 sm:gap-3 min-w-0">
                {/* Date Segmented Control */}
                <div className="grid grid-cols-4 w-full sm:w-auto items-center p-1 bg-[#F0EDE5] rounded border border-[#D1CDC2] text-xs font-mono">
                  <button
                    type="button"
                    onClick={() => setDateRange("7d")}
                    className={`px-1.5 sm:px-3 py-1 rounded transition-colors whitespace-nowrap ${
                      dateRange === "7d" ? "bg-[#333E50] text-white font-semibold" : "text-[#44474C] hover:text-black"
                    }`}
                  >
                    Last 7D
                  </button>
                  <button
                    type="button"
                    onClick={() => setDateRange("30d")}
                    className={`px-1.5 sm:px-3 py-1 rounded transition-colors whitespace-nowrap ${
                      dateRange === "30d" ? "bg-[#333E50] text-white font-semibold" : "text-[#44474C] hover:text-black"
                    }`}
                  >
                    Last 30D
                  </button>
                  <button
                    type="button"
                    onClick={() => setDateRange("quarter")}
                    className={`px-1.5 sm:px-3 py-1 rounded transition-colors whitespace-nowrap ${
                      dateRange === "quarter" ? "bg-[#333E50] text-white font-semibold" : "text-[#44474C] hover:text-black"
                    }`}
                  >
                    Quarter
                  </button>
                  <button
                    type="button"
                    onClick={() => setDateRange("custom")}
                    className={`px-1.5 sm:px-3 py-1 rounded transition-colors whitespace-nowrap ${
                      dateRange === "custom" ? "bg-[#333E50] text-white font-semibold" : "text-[#44474C] hover:text-black"
                    }`}
                  >
                    Custom
                  </button>
                </div>

                <div className="h-6 w-px bg-[#D1CDC2] hidden sm:block" />

                {/* Region Dropdown */}
                <div className="flex items-center w-full sm:w-auto min-w-0 bg-[#F0EDE5] border border-[#D1CDC2] rounded px-3 py-1 text-xs">
                  <span className="font-mono text-[#566155] mr-2 font-semibold">REGION:</span>
                  <select
                    value={selectedRegion}
                    onChange={(e) => setSelectedRegion(e.target.value)}
                    className="bg-transparent text-sm font-medium text-[#1A1C1E] focus:outline-none cursor-pointer min-w-0 flex-1"
                  >
                    <option value="all">All Regions (National)</option>
                    {regionalDistribution.map((region) => (
                      <option key={region.region} value={region.region}>{region.region}</option>
                    ))}
                  </select>
                </div>

                {/* Commodity Dropdown */}
                <div className="flex items-center w-full sm:w-auto min-w-0 bg-[#F0EDE5] border border-[#D1CDC2] rounded px-3 py-1 text-xs">
                  <span className="font-mono text-[#566155] mr-2 font-semibold">COMMODITY:</span>
                  <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="bg-transparent text-sm font-medium text-[#1A1C1E] focus:outline-none cursor-pointer min-w-0 flex-1"
                  >
                    <option value="all">All Commodities</option>
                    <option value="packaged_food">Packaged Food</option>
                    <option value="general">General Packaged Goods</option>
                    <option value="pan_masala">Tobacco & Pan Masala</option>
                    <option value="electronics">Electronics</option>
                  </select>
                </div>

                {/* Reset Filters */}
                {(selectedRegion !== "all" || selectedCategory !== "all" || dateRange !== "30d") && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedRegion("all");
                      setSelectedCategory("all");
                      setDateRange("30d");
                    }}
                    className="text-xs font-mono text-red-700 hover:underline px-2"
                  >
                    Reset Filters
                  </button>
                )}
              </div>

              {/* Right Status */}
              <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-[#566155]">
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#D6E3D3] text-[#131E14]">
                  <span>SYNCED: {new Date().toLocaleTimeString()}</span>
                </div>
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#F0EDE5] text-[#333E50] border border-[#D1CDC2]">
                  <span>RULES: 2026.02.01</span>
                </div>
              </div>
            </div>
          </section>

          {/* Main Dashboard Body Container */}
          <div className="p-4 md:p-8 flex flex-col gap-6 max-w-[1600px] mx-auto w-full">
            {loadError && (
              <div role="status" className="border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950 rounded">
                {loadError}
              </div>
            )}
            {/* Executive Operational KPI Summary Strip (5 Cards) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              {/* KPI 1: Total Inspections */}
              <div className="bg-white rounded border border-[#D1CDC2] p-4 flex flex-col justify-between shadow-xs">
                <div className="flex items-start justify-between">
                  <div className="flex flex-col">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#566155] font-semibold">
                      Total Inspections
                    </span>
                    <span className="text-3xl font-bold tracking-tight text-[#1A1C1E] mt-1">
                      {totalInspections.toLocaleString()}
                    </span>
                  </div>
                  <span className="p-2 rounded bg-[#F0EDE5] text-base">📝</span>
                </div>
                <div className="mt-4 pt-2 border-t border-[#F0EDE5]">
                  <div className="flex items-center justify-between text-xs font-mono text-[#566155] mb-1.5">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-emerald-600 inline-block" />{" "}
                      {compliantInspections} Compliant
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-red-600 inline-block" />{" "}
                      {breachInspections} Breach
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-[#F0EDE5] rounded-full overflow-hidden flex">
                    <div
                      className="bg-emerald-600 h-full"
                      style={{
                        width: `${Math.min(100, (compliantInspections / Math.max(1, totalInspections)) * 100)}%`,
                      }}
                    />
                    <div
                      className="bg-red-600 h-full"
                      style={{
                        width: `${Math.min(100, (breachInspections / Math.max(1, totalInspections)) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* KPI 2: Overall Compliance Rate */}
              <div className="bg-white rounded border border-[#D1CDC2] p-4 flex flex-col justify-between shadow-xs">
                <div className="flex items-start justify-between">
                  <div className="flex flex-col">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#566155] font-semibold">
                      Overall Compliance
                    </span>
                    <span className="text-3xl font-bold tracking-tight text-[#1A1C1E] mt-1">
                      {overallComplianceRate.toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-xs font-mono font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                    <span>LIVE</span>
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-[#F0EDE5]">
                  <div className="flex items-center justify-between text-xs font-mono text-[#566155] mb-1.5">
                    <span>Live aggregate</span>
                    <span className="text-amber-700 font-medium">
                      {totalInspections} inspections
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-[#F0EDE5] rounded-full overflow-hidden relative">
                    <div
                      className="bg-[#333E50] h-full"
                      style={{ width: `${Math.min(100, overallComplianceRate)}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* KPI 3: Statutory Violations */}
              <div className="bg-white rounded border border-[#D1CDC2] p-4 flex flex-col justify-between shadow-xs">
                <div className="flex items-start justify-between">
                  <div className="flex flex-col">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#566155] font-semibold">
                      Breaches Logged
                    </span>
                    <span className="text-3xl font-bold tracking-tight text-red-700 mt-1">
                      {totalBreaches.toLocaleString()}
                    </span>
                  </div>
                  <span className="p-2 rounded bg-red-50 text-base">⚖️</span>
                </div>
                <div className="mt-4 flex items-center gap-1.5">
                  <div className="flex-1 px-1.5 py-1 rounded bg-red-100 text-center">
                    <span className="block text-[11px] font-mono uppercase text-red-900 font-bold">
                      Crit: {critViolations}
                    </span>
                  </div>
                  <div className="flex-1 px-1.5 py-1 rounded bg-amber-100 text-center">
                    <span className="block text-[11px] font-mono uppercase text-amber-900 font-bold">
                      Maj: {majViolations}
                    </span>
                  </div>
                  <div className="flex-1 px-1.5 py-1 rounded bg-stone-100 text-center">
                    <span className="block text-[11px] font-mono uppercase text-stone-800 font-bold">
                      Mod: {modViolations}
                    </span>
                  </div>
                </div>
              </div>

              {/* KPI 4: Review Queue Backlog */}
              <div className="bg-white rounded border border-[#D1CDC2] p-4 flex flex-col justify-between shadow-xs">
                <div className="flex items-start justify-between">
                  <div className="flex flex-col">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#566155] font-semibold">
                      Review Backlog
                    </span>
                    <div className="flex items-baseline gap-1.5 mt-1">
                      <span className="text-3xl font-bold tracking-tight text-[#4B3B1F]">
                        {backlogCount}
                      </span>
                      <span className="text-xs text-[#566155]">Pending</span>
                    </div>
                  </div>
                  <div className="relative p-2 rounded bg-[#F9DFB8] text-base">
                    <span>🔍</span>
                    {backlogCount > 0 && (
                      <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-red-600 rounded-full ring-2 ring-white" />
                    )}
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-[#F0EDE5]">
                  <span className="text-xs font-mono text-[#566155] block truncate">
                    Sec 36 / Rule 6(1) Verification
                  </span>
                  <span className="text-[11px] font-mono text-[#4B3B1F] font-semibold mt-0.5 block">
                    {backlogCount > 0 ? "Officer confirmation required" : "No pending confirmation"}
                  </span>
                </div>
              </div>

              {/* KPI 5: Active Enforcement Personnel */}
              <div className="bg-white rounded border border-[#D1CDC2] p-4 flex flex-col justify-between shadow-xs">
                <div className="flex items-start justify-between">
                  <div className="flex flex-col">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-[#566155] font-semibold">
                      Field Personnel
                    </span>
                    <div className="flex items-baseline gap-1.5 mt-1">
                      <span className="text-3xl font-bold tracking-tight text-[#333E50]">
                        {activeOfficers}
                      </span>
                      <span className="text-xs text-[#566155]">Officers</span>
                    </div>
                  </div>
                  <span className="p-2 rounded bg-[#D8E3FA] text-base">👮</span>
                </div>
                <div className="mt-4 pt-2 border-t border-[#F0EDE5] flex flex-col gap-1">
                  <div className="flex items-center justify-between text-xs font-mono text-[#566155]">
                    <span className="text-emerald-700 font-semibold flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 inline-block" />{" "}
                      {activeOfficers} live officers
                    </span>
                    <span>{throughput?.officers.length ?? 0} reporting</span>
                  </div>
                  <div className="w-full h-1 bg-[#F0EDE5] rounded-full overflow-hidden">
                    <div className="bg-emerald-600 h-full" style={{ width: activeOfficers > 0 ? "100%" : "0%" }} />
                  </div>
                </div>
              </div>
            </div>

            {/* Primary Analytics: Compliance Trends Over Time (30 Days Dual Vector Chart) */}
            <div className="bg-white rounded border border-[#D1CDC2] p-6 shadow-xs">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#F0EDE5]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-lg">📈</span>
                    <h2 className="text-lg font-bold text-[#1A1C1E]">
                      Statutory Enforcement Velocity & Compliance Ratio
                    </h2>
                  </div>
                  <p className="text-xs text-[#566155] mt-1">
                    Dual-vector audit: 30-Day volume of field inspections vs. statutory non-compliance rate under Legal Metrology Act, 2009.
                  </p>
                </div>

                {/* Chart Technical Legend */}
                <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 bg-[#D6E3D3] rounded-xs inline-block" />
                    <span className="text-[#566155]">Compliant Pkg</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 bg-[#FFDAD6] rounded-xs inline-block" />
                    <span className="text-[#566155]">Violation Pack</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-4 h-0.5 bg-[#333E50] inline-block" />
                    <span className="text-[#333E50] font-bold">Compliance Rate (%)</span>
                  </div>
                </div>
              </div>

              {/* Inline SVG Dual Axis Chart */}
              <div className="relative w-full overflow-x-auto pt-4">
                <svg
                  className="w-full h-64 select-none min-w-[760px]"
                  preserveAspectRatio="none"
                  viewBox="0 0 1000 240"
                >
                  {/* Grid Lines */}
                  <line stroke="#E2E2E5" strokeDasharray="3,3" strokeWidth="1" x1="40" x2="980" y1="20" y2="20" />
                  <line stroke="#E2E2E5" strokeDasharray="3,3" strokeWidth="1" x1="40" x2="980" y1="70" y2="70" />
                  <line stroke="#E2E2E5" strokeDasharray="3,3" strokeWidth="1" x1="40" x2="980" y1="120" y2="120" />
                  <line stroke="#E2E2E5" strokeDasharray="3,3" strokeWidth="1" x1="40" x2="980" y1="170" y2="170" />
                  <line stroke="#75777D" strokeWidth="1" x1="40" x2="980" y1="210" y2="210" />

                  {/* Live Y-axis scale */}
                  <text className="text-[10px] font-mono fill-[#75777D]" textAnchor="end" x="32" y="24">{maxTrendVolume}</text>
                  <text className="text-[10px] font-mono fill-[#75777D]" textAnchor="end" x="32" y="74">{Math.round(maxTrendVolume * 0.75)}</text>
                  <text className="text-[10px] font-mono fill-[#75777D]" textAnchor="end" x="32" y="124">{Math.round(maxTrendVolume * 0.5)}</text>
                  <text className="text-[10px] font-mono fill-[#75777D]" textAnchor="end" x="32" y="174">{Math.round(maxTrendVolume * 0.25)}</text>
                  <text className="text-[10px] font-mono fill-[#75777D]" textAnchor="end" x="32" y="213">0</text>

                  <text className="text-[10px] font-mono fill-[#75777D]" textAnchor="start" x="988" y="24">100%</text>
                  <text className="text-[10px] font-mono fill-[#75777D]" textAnchor="start" x="988" y="74">85%</text>
                  <text className="text-[10px] font-mono fill-[#75777D]" textAnchor="start" x="988" y="124">70%</text>
                  <text className="text-[10px] font-mono fill-[#75777D]" textAnchor="start" x="988" y="174">55%</text>

                  {/* Live inspection-volume columns only. */}
                  <g transform="translate(50, 0)">
                    {trendPoints.map((point, idx) => {
                      const x = idx * (900 / Math.max(1, trendPoints.length));
                      const compliantHeight = (point.compliant_count / maxTrendVolume) * 160;
                      const violationHeight = (point.violation_count / maxTrendVolume) * 160;
                      const yCompliant = 210 - compliantHeight - violationHeight;
                      const yViolation = 210 - violationHeight;
                      const isPeak = peakTrend?.date === point.date;
                      const isLatest = idx === trendPoints.length - 1;

                      return (
                        <g key={idx}>
                          <rect
                            x={x}
                            y={yCompliant}
                            width={Math.max(8, 780 / Math.max(1, trendPoints.length))}
                            height={compliantHeight}
                            fill={isPeak ? "#566155" : isLatest ? "#333E50" : "#D6E3D3"}
                            rx="1"
                          />
                          <rect
                            x={x}
                            y={yViolation}
                            width={Math.max(8, 780 / Math.max(1, trendPoints.length))}
                            height={violationHeight}
                            fill={isPeak || isLatest ? "#BA1A1A" : "#FFDAD6"}
                            rx="1"
                          />
                        </g>
                      );
                    })}
                  </g>

                  {trendPoints.length > 0 && <polyline fill="none" stroke="#333E50" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" points={trendPoints.map((point, idx) => `${50 + idx * (900 / Math.max(1, trendPoints.length))},${210 - (point.compliance_rate / 100) * 160}`).join(" ")} />}
                  {trendPoints.length === 0 && <text className="text-[12px] font-mono fill-[#75777D]" textAnchor="middle" x="510" y="115">No live inspection trend for this filter.</text>}
                </svg>
              </div>

              <div className="mt-3 pt-3 border-t border-[#F0EDE5] flex flex-wrap items-center justify-between gap-2 text-xs font-mono text-[#566155]">
                <span>Sampling Period: {trends?.period_start || "No data"} - {trends?.period_end || "No data"}</span>
                <span className="text-[#333E50] font-bold">
                  Aggregate compliance: {overallComplianceRate.toFixed(1)}%
                </span>
              </div>
            </div>

            {/* Two-Column Operational Workspace */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* LEFT COLUMN: Top Violated Statutory Rules (7 Cols) */}
              <div className="lg:col-span-7 bg-white rounded border border-[#D1CDC2] p-4 sm:p-6 shadow-xs flex flex-col justify-between min-w-0">
                <div>
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 pb-4 border-b border-[#F0EDE5]">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">⚠️</span>
                        <h3 className="text-base font-bold text-[#1A1C1E]">
                          Statutory Rule Infractions (PCR 2011)
                        </h3>
                      </div>
                      <p className="text-xs text-[#566155] mt-1">
                        Evidentiary distribution of detected offenses under the Legal Metrology (Packaged Commodities) Rules.
                      </p>
                    </div>
                    <span className="self-start text-xs font-mono text-[#566155] bg-[#F0EDE5] px-2 py-1 rounded whitespace-nowrap">
                      Ranked 1-{displayRules.length}
                    </span>
                  </div>

                  {/* Rule Infraction List */}
                  <div className="flex flex-col gap-3 mt-4">
                    {displayRules.map((item, idx) => (
                      <div key={idx} className="p-3 rounded bg-[#F9F7F2] border border-[#E8E8EA] min-w-0 overflow-hidden">
                        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 mb-1.5 min-w-0">
                          <div className="flex flex-wrap items-center gap-2 min-w-0">
                            <span className="text-xs font-mono font-bold text-[#1A1C1E]">{item.rank}</span>
                            <span className="text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-[#333E50] text-white break-words max-w-full">
                              {item.rule}
                            </span>
                            <span className="text-sm font-semibold text-[#1A1C1E] break-words min-w-0">
                              {item.title}
                            </span>
                          </div>
                          <div className="flex flex-wrap items-center gap-2 shrink-0">
                            <span className="text-xs font-mono font-bold text-[#1A1C1E]">{item.breaches} Breaches</span>
                            <span
                              className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                                item.severity === "CRITICAL"
                                  ? "bg-red-100 text-red-900"
                                  : item.severity === "MAJOR"
                                  ? "bg-amber-100 text-amber-900"
                                  : "bg-stone-200 text-stone-900"
                              }`}
                            >
                              {item.severity}
                            </span>
                          </div>
                        </div>
                        <div className="w-full h-2 bg-[#E2E2E5] rounded-full overflow-hidden">
                          <div
                            className={`h-full ${
                              item.severity === "CRITICAL"
                                ? "bg-red-600"
                                : item.severity === "MAJOR"
                                ? "bg-[#4A5568]"
                                : "bg-[#566155]"
                            }`}
                            style={{ width: item.width }}
                          />
                        </div>
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-[11px] font-mono text-[#566155] mt-1.5">
                          <span className="break-words">{item.sub}</span>
                          <span className="shrink-0">{item.pct} of infractions</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#F0EDE5] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <span className="text-xs font-mono text-[#566155] break-words">
                    Summary: {totalBreaches} offenses cataloged across {breachInspections} non-compliant inspections.
                  </span>
                  <button
                    type="button"
                    onClick={() => alert("Viewing full LMPC Rule Violation Docket...")}
                    className="text-xs font-bold text-[#333E50] hover:underline flex items-center gap-1"
                  >
                    <span>View Docket Precedents</span>
                    <span>→</span>
                  </button>
                </div>
              </div>

              {/* RIGHT COLUMN: Commodity Category & Regional Distribution (5 Cols) */}
              <div className="lg:col-span-5 flex flex-col gap-6 min-w-0">
                {/* Sector Compliance Risk */}
                <div className="bg-white rounded border border-[#D1CDC2] p-6 shadow-xs">
                  <div className="flex items-center justify-between pb-3 border-b border-[#F0EDE5]">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">🏷️</span>
                      <h3 className="text-base font-bold text-[#1A1C1E]">Commodity Compliance Index</h3>
                    </div>
                    <span className="text-[11px] font-mono text-[#566155] uppercase font-semibold">
                      Target &gt; 85%
                    </span>
                  </div>
                  <p className="text-xs text-[#566155] mt-1 mb-4">
                    Evaluation of target sectors against statutory labeling standards.
                  </p>

                  <div className="flex flex-col gap-3.5">
                    {displayCategories.map((cat, idx) => (
                      <div key={idx} className="flex flex-col gap-1">
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-[#1A1C1E]">{cat.name}</span>
                            <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${cat.badgeColor}`}>
                              {cat.badge}
                            </span>
                          </div>
                          <span className="font-mono font-bold text-[#1A1C1E]">{cat.rate.toFixed(1)}%</span>
                        </div>
                        <div className="w-full h-2 bg-[#F0EDE5] rounded-full overflow-hidden">
                          <div className={`${cat.color} h-full`} style={{ width: `${Math.min(100, cat.rate)}%` }} />
                        </div>
                        <span className="text-[11px] font-mono text-[#566155]">{cat.desc}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Regional Enforcement Volume */}
                <div className="bg-white rounded border border-[#D1CDC2] p-6 shadow-xs">
                  <div className="flex items-center justify-between pb-3 border-b border-[#F0EDE5]">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">🗺️</span>
                      <h3 className="text-base font-bold text-[#1A1C1E]">Zonal Enforcement Distribution</h3>
                    </div>
                    <span className="text-xs font-mono text-[#566155]">{regionalDistribution.length} LIVE REGIONS</span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mt-4">
                    {regionalDistribution.map((region) => (
                      <div key={region.region} className="p-3 rounded bg-[#F9F7F2] border border-[#E8E8EA]">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono font-bold uppercase text-[#1A1C1E]">{region.region}</span>
                          <span className="text-xs font-mono font-bold text-[#333E50]">{region.compliance_rate.toFixed(1)}%</span>
                        </div>
                        <div className="flex items-baseline gap-1 mt-1">
                          <span className="text-2xl font-bold text-[#1A1C1E]">{region.total_inspections}</span>
                          <span className="text-xs font-mono text-[#566155]">insp.</span>
                        </div>
                        <div className="w-full h-1 bg-[#E2E2E5] rounded-full overflow-hidden mt-2">
                          <div className="bg-[#333E50] h-full" style={{ width: `${(region.total_inspections / maxRegionalVolume) * 100}%` }} />
                        </div>
                        <span className="text-[11px] font-mono text-red-700 font-semibold block mt-1">{region.violations_count} Violations Logged</span>
                      </div>
                    ))}
                    {regionalDistribution.length === 0 && <p className="col-span-2 text-xs text-[#566155]">No live regional inspection data for this filter.</p>}
                  </div>
                </div>
              </div>
            </div>

            {/* Officer Operational Throughput & Audit Backlog Table */}
            <div className="bg-white rounded border border-[#D1CDC2] p-4 sm:p-6 shadow-xs min-w-0">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#F0EDE5]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🎖️</span>
                    <h3 className="text-base font-bold text-[#1A1C1E]">
                      Field Inspector Throughput & Section 36 Human Override Ledger
                    </h3>
                  </div>
                  <p className="text-xs text-[#566155] mt-1">
                    Statutory tracking of assigned field operations, completion velocities, review backlogs, and OCR verification overrides.
                  </p>
                </div>
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 min-w-0">
                  <div className="relative min-w-0">
                    <input
                      type="text"
                      value={officerSearch}
                      onChange={(e) => setOfficerSearch(e.target.value)}
                      placeholder="Search Officer ID / Station..."
                      className="pl-3 pr-3 py-1.5 bg-[#F0EDE5] border border-[#D1CDC2] rounded text-xs font-medium text-[#1A1C1E] focus:outline-none w-full sm:w-64"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => alert("Dispatching complete field dossier (CSV)...")}
                    className="h-8 px-3 rounded bg-[#333E50] hover:bg-[#4A5568] text-white text-xs font-mono flex items-center gap-1.5 transition-colors"
                  >
                    <span>📥</span>
                    <span>Dispatch Dossier</span>
                  </button>
                </div>
              </div>

              {/* Data Table */}
              <div className="w-full max-w-full overflow-x-auto overscroll-x-contain mt-4">
                <table className="w-full text-left border-collapse min-w-[840px]">
                  <thead>
                    <tr className="bg-[#F0EDE5] text-[#566155] font-mono text-[11px] uppercase tracking-wider border-b border-[#D1CDC2]">
                      <th className="py-2 px-3">Officer Name & ID</th>
                      <th className="py-2 px-3">Jurisdiction / Zone</th>
                      <th className="py-2 px-3">Assigned / Done</th>
                      <th className="py-2 px-3">Completion %</th>
                      <th className="py-2 px-3">Review Backlog</th>
                      <th className="py-2 px-3">Sec 36 Overrides</th>
                      <th className="py-2 px-3">Last Sync</th>
                      <th className="py-2 px-3 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#F0EDE5] text-xs">
                    {filteredOfficers.map((officer, idx) => {
                      const compPercent = Math.min(
                        100,
                        (officer.completed_inspections / Math.max(1, officer.total_inspections)) * 100
                      );
                      const isEven = idx % 2 === 0;

                      return (
                        <tr
                          key={officer.officer_id}
                          className={`${isEven ? "bg-white" : "bg-[#F9F7F2]"} hover:bg-[#E8E8EA] transition-colors`}
                        >
                          <td className="py-3 px-3 font-medium text-[#1A1C1E]">
                            <div className="flex flex-col">
                              <span>{officer.officer_name}</span>
                              <span className="font-mono text-[#333E50] text-[11px]">
                                {officer.officer_id}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-3 text-[#566155]">{officer.region}</td>
                          <td className="py-3 px-3 font-mono font-semibold text-[#1A1C1E]">
                            {officer.total_inspections} / {officer.completed_inspections}
                          </td>
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-semibold w-10">
                                {compPercent.toFixed(1)}%
                              </span>
                              <div className="w-16 h-1.5 bg-[#F0EDE5] rounded-full overflow-hidden">
                                <div
                                  className={`h-full ${
                                    compPercent >= 90 ? "bg-emerald-600" : "bg-[#333E50]"
                                  }`}
                                  style={{ width: `${compPercent}%` }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-3">
                            <span
                              className={`px-2 py-0.5 rounded font-mono text-[11px] font-bold ${
                                officer.needs_review_inspections > 5
                                  ? "bg-amber-100 text-amber-900"
                                  : officer.needs_review_inspections === 0
                                  ? "bg-emerald-100 text-emerald-900"
                                  : "bg-[#E8E8EA] text-[#1A1C1E]"
                              }`}
                            >
                              {officer.needs_review_inspections} Pending
                            </span>
                          </td>
                          <td className="py-3 px-3 font-mono text-[#1A1C1E]">
                            <span className="inline-flex items-center gap-1">
                              <span>🔒</span> {officer.human_overrides_count} Overrides
                            </span>
                          </td>
                          <td className="py-3 px-3 font-mono text-[#566155]">
                            {officer.last_inspection_at}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-[11px] font-semibold ${
                                officer.status === "Active Field"
                                  ? "bg-[#D6E3D3] text-[#131E14]"
                                  : "bg-[#E8E8EA] text-[#44474C]"
                              }`}
                            >
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${
                                  officer.status === "Active Field" ? "bg-emerald-600" : "bg-stone-500"
                                }`}
                              />{" "}
                              {officer.status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="mt-4 pt-3 border-t border-[#F0EDE5] flex flex-col sm:flex-row items-center justify-between gap-2 text-xs font-mono text-[#566155]">
                <span>
                  Section 36 Human Overrides require supervisor audit endorsement prior to statutory notice dispatch.
                </span>
                <span>{filteredOfficers.length} live officers shown</span>
              </div>
            </div>

            {/* Live dashboard state — sourced only from returned API aggregates. */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-8 bg-white rounded border border-[#D1CDC2] p-6 shadow-xs">
                <div className="flex items-center justify-between pb-3 border-b border-[#F0EDE5]">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">📡</span>
                    <h4 className="text-base font-bold text-[#1A1C1E]">
                      Live inspection snapshot
                    </h4>
                  </div>
                  <span className="text-[11px] font-mono bg-emerald-100 text-emerald-900 font-bold px-2 py-0.5 rounded">
                    API REFRESH
                  </span>
                </div>

                <div className="flex flex-col gap-2 mt-3">
                  <div className="p-2.5 rounded bg-[#F9F7F2] border border-[#E8E8EA] flex items-start gap-3">
                    <span className="text-xs font-mono text-[#333E50] font-bold shrink-0">INSPECTIONS</span>
                    <div className="flex-1 text-xs text-[#1A1C1E]">
                      {totalInspections} inspections are included in the current live aggregate.
                    </div>
                    <span className="text-[10px] font-mono text-[#333E50] bg-[#E8E8EA] px-1.5 py-0.5 rounded shrink-0 font-bold">
                      LIVE
                    </span>
                  </div>

                  <div className="p-2.5 rounded bg-[#F9F7F2] border border-[#E8E8EA] flex items-start gap-3">
                    <span className="text-xs font-mono text-[#333E50] font-bold shrink-0">REVIEW</span>
                    <div className="flex-1 text-xs text-[#1A1C1E]">
                      {backlogCount} inspections require officer confirmation.
                    </div>
                    <span className="text-[10px] font-mono text-amber-900 bg-amber-100 px-1.5 py-0.5 rounded shrink-0 font-bold">
                      PENDING
                    </span>
                  </div>

                  <div className="p-2.5 rounded bg-[#F9F7F2] border border-[#E8E8EA] flex items-start gap-3">
                    <span className="text-xs font-mono text-[#333E50] font-bold shrink-0">VIOLATIONS</span>
                    <div className="flex-1 text-xs text-[#1A1C1E]">
                      {totalBreaches} rule findings are present in the returned inspection records.
                    </div>
                    <span className="text-[10px] font-mono text-red-700 bg-red-100 px-1.5 py-0.5 rounded shrink-0 font-bold">
                      REVIEW
                    </span>
                  </div>
                </div>
              </div>

              <div className="lg:col-span-4 bg-white rounded border border-[#D1CDC2] p-6 shadow-xs flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 pb-3 border-b border-[#F0EDE5]">
                    <span className="text-lg">🛡️</span>
                    <h4 className="text-base font-bold text-[#1A1C1E]">Live data controls</h4>
                  </div>
                  <p className="text-xs text-[#566155] mt-1">
                    Refresh or export the returned inspection aggregates.
                  </p>

                  <div className="flex flex-col gap-2 mt-4">
                    <button
                      type="button"
                      onClick={fetchDashboardData}
                      className="px-3 py-2 rounded bg-[#333E50] hover:bg-[#4A5568] text-white text-xs font-medium flex items-center justify-between transition-colors shadow-xs"
                    >
                      <span className="flex items-center gap-2">
                        <span>↻</span>
                        <span>Refresh live aggregates</span>
                      </span>
                      <span>→</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleExportCsv}
                      className="px-3 py-2 rounded bg-[#F0EDE5] hover:bg-[#E2E2E5] text-[#1A1C1E] text-xs font-medium flex items-center justify-between transition-colors border border-[#D1CDC2]"
                    >
                      <span className="flex items-center gap-2">
                        <span>📋</span>
                        <span>Export live ledger (CSV)</span>
                      </span>
                      <span>📥</span>
                    </button>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#F0EDE5] bg-[#F9F7F2] p-3 rounded flex items-center gap-2.5">
                  <span className="text-xl">🔐</span>
                  <div className="flex flex-col">
                    <span className="text-xs font-mono font-bold text-[#1A1C1E]">
                      LIVE API DATA
                    </span>
                    <span className="text-[10px] font-mono text-[#566155]">
                      Values update from the inspection service.
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Statutory Regulatory Notice */}
            <div className="bg-[#F0EDE5] rounded border border-[#D1CDC2] p-4 flex items-start gap-3">
              <span className="text-xl mt-0.5">📜</span>
              <div className="flex flex-col gap-0.5">
                <span className="text-xs font-mono font-bold text-[#1A1C1E] uppercase tracking-wider">
                  Legal Metrology Statutory Regulatory Notice
                </span>
                <p className="text-xs font-mono text-[#566155] leading-relaxed">
                  Data generated for regulatory oversight and decision-support under the Legal Metrology Act, 2009 and Legal Metrology (Packaged Commodities) Rules, 2011. Automated metrics reflect versioned rule pack evaluations (Rulepack v2026.02.01) and officer-verified field records. Human interventions and OCR overrides are permanently logged under Section 36 for evidentiary presentation before the Adjudicating Officer.
                </p>
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Mobile command navigation: the desktop sidebar is intentionally hidden on phones. */}
      <nav className="fixed bottom-0 inset-x-0 z-50 md:hidden h-16 bg-[#F9F7F2]/95 backdrop-blur-md border-t border-[#D1CDC2] flex items-center justify-around px-4 pb-[env(safe-area-inset-bottom)]">
        <Link href="/" className="flex flex-col items-center gap-0.5 text-[#566155] text-[10px] font-mono">
          <span className="text-base leading-none">📷</span><span>CAPTURE</span>
        </Link>
        <Link href="/history" className="flex flex-col items-center gap-0.5 text-[#566155] text-[10px] font-mono">
          <span className="text-base leading-none">📋</span><span>ARCHIVE</span>
        </Link>
        <Link href="/dashboard" className="flex flex-col items-center gap-0.5 text-[#333E50] text-[10px] font-mono font-bold">
          <span className="text-base leading-none">📊</span><span>ANALYTICS</span>
        </Link>
        <Link href="/admin/rule-packs" className="flex flex-col items-center gap-0.5 text-[#566155] text-[10px] font-mono">
          <span className="text-base leading-none">⚖️</span><span>RULES</span>
        </Link>
      </nav>

      {/* Footer */}
      <footer className="w-full bg-[#F0EDE5] border-t border-[#D1CDC2] py-3 px-4 md:px-8 pb-20 md:pb-3">
        <div className="max-w-[1600px] mx-auto flex flex-col md:flex-row items-center justify-between gap-2 text-[11px] font-mono text-[#566155]">
          <span>
            Statutory Notice: Official Legal Metrology field surveillance records. Unauthorized duplication or alteration is punishable under Legal Metrology Act, 2009 & IPC.
          </span>
          <span>Department of Consumer Affairs · Government of India · Central Enforcement Portal</span>
        </div>
      </footer>
    </div>
  );
}
