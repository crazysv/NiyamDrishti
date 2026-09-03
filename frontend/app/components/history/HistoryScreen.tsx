/* eslint-disable @next/next/no-img-element */
"use client";

import React, { useState, useEffect, useCallback, useTransition } from "react";
import Link from "next/link";
import {
  Camera,
  History as HistoryIcon,
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  User,
  Wifi,
  WifiOff,
  CloudUpload,
  ChevronRight,
} from "lucide-react";
import { searchInspections } from "../../services/inspectionService";
import { InspectionSummary, InspectionSearchParams } from "../../types/inspection";
import { useOfflineQueue } from "../../hooks/useOfflineQueue";
import { getPendingInspections } from "../../db/dexie";

function useOnlineStatus() {
  return React.useSyncExternalStore(
    (callback) => {
      window.addEventListener("online", callback);
      window.addEventListener("offline", callback);
      return () => {
        window.removeEventListener("online", callback);
        window.removeEventListener("offline", callback);
      };
    },
    () => (typeof navigator !== "undefined" ? navigator.onLine : true),
    () => true
  );
}

type ActiveFilterChip = "all" | "violations" | "offline" | "packaged_food" | "electronics" | "today";

export default function HistoryScreen() {
  const isOnline = useOnlineStatus();
  const { pendingCount, syncNow, isSyncing } = useOfflineQueue();

  const [searchQuery, setSearchQuery] = useState("");
  const [activeChip, setActiveChip] = useState<ActiveFilterChip>("all");
  const [inspections, setInspections] = useState<InspectionSummary[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      if (activeChip === "offline") {
        // Load offline records from IndexedDB
        const pendingRecords = await getPendingInspections();
        const mapped: InspectionSummary[] = pendingRecords.map(({ inspection, images }) => {
          const frontImg = images.find((img) => img.imageRole === "front_pdp") || images[0];
          return {
            id: inspection.id,
            officer_id: "local_officer",
            officer_name: "Local Officer",
            status: inspection.status,
            commodity_category: inspection.commodityCategory,
            rule_pack_version: "2026.02.01",
            region: "Local Device",
            captured_offline: true,
            created_at: inspection.createdAt,
            updated_at: inspection.updatedAt,
            violations_count: 0,
            fields_count: 0,
            images_count: images.length,
            thumbnail_url: frontImg?.dataUrl,
            overall_verdict: "needs_review",
          };
        });

        // Filter by text search if present
        const filtered = searchQuery.trim()
          ? mapped.filter(
              (item) =>
                item.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
                (item.commodity_category &&
                  item.commodity_category.toLowerCase().includes(searchQuery.toLowerCase()))
            )
          : mapped;

        setInspections(filtered);
        setTotalCount(filtered.length);
      } else {
        // Build API query parameters
        const params: InspectionSearchParams = {
          limit: 50,
          skip: 0,
        };

        if (searchQuery.trim()) {
          params.product_query = searchQuery.trim();
        }

        if (activeChip === "violations") {
          params.has_violations = true;
        } else if (activeChip === "packaged_food") {
          params.commodity_category = "packaged_food";
        } else if (activeChip === "electronics") {
          params.commodity_category = "electronics";
        } else if (activeChip === "today") {
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          params.date_from = today.toISOString();
        }

        const data = await searchInspections(params);
        setInspections(data.items);
        setTotalCount(data.total);
      }
    } catch {
      // If API fails (e.g. offline), fallback to IndexedDB records
      try {
        const pendingRecords = await getPendingInspections();
        const mapped: InspectionSummary[] = pendingRecords.map(({ inspection, images }) => {
          const frontImg = images.find((img) => img.imageRole === "front_pdp") || images[0];
          return {
            id: inspection.id,
            officer_id: "local_officer",
            officer_name: "Local Officer",
            status: inspection.status,
            commodity_category: inspection.commodityCategory,
            rule_pack_version: "2026.02.01",
            region: "Offline Cache",
            captured_offline: true,
            created_at: inspection.createdAt,
            updated_at: inspection.updatedAt,
            violations_count: 0,
            fields_count: 0,
            images_count: images.length,
            thumbnail_url: frontImg?.dataUrl,
            overall_verdict: "needs_review",
          };
        });
        setInspections(mapped);
        setTotalCount(mapped.length);
      } catch {
        setErrorMessage("Unable to load inspection history.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [activeChip, searchQuery]);

  useEffect(() => {
    startTransition(() => {
      loadData();
    });
  }, [loadData]);

  return (
    <div className="flex flex-col w-full max-w-md mx-auto min-h-screen bg-[#F9F7F2] text-[#1A1C1E] shadow-2xl relative select-none">
      {/* Top App Header */}
      <header className="sticky top-0 z-40 bg-[#F9F7F2]/90 backdrop-blur-md border-b border-[#D1CDC2] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded bg-[#333E50] flex items-center justify-center text-white font-mono text-xs shadow-sm font-bold">
            ND
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-base tracking-tight leading-none text-[#1A1C1E]">
              NiyamDrishti
            </span>
            <span className="font-mono text-[10px] text-[#75777D] tracking-wider uppercase mt-0.5">
              Evidence System
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Status Pill */}
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium border ${
              isOnline
                ? "bg-[#D6E3D3] text-[#3E4A3E] border-[#BDCABA]"
                : "bg-[#FFDAD6] text-[#93000a] border-[#FFB4AB]"
            }`}
          >
            {isOnline ? (
              <>
                <Wifi className="w-3.5 h-3.5" />
                <span>ONLINE</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5" />
                <span>OFFLINE</span>
              </>
            )}
          </div>

          <button
            type="button"
            aria-label="Officer Profile"
            className="w-8 h-8 rounded-full bg-[#333E50] flex items-center justify-center text-white shadow-sm hover:opacity-90 active:scale-95"
          >
            <User className="w-4 h-4 text-white" />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto px-4 pt-3 pb-24">
        {/* Title Bar */}
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-xl font-bold text-[#1A1C1E] tracking-tight">
              Inspection Archive
            </h1>
            <p className="text-xs text-[#75777D] font-mono mt-0.5">
              {totalCount} Total records · {pendingCount} pending device sync
            </p>
          </div>
          <button
            type="button"
            onClick={loadData}
            title="Refresh Inspections"
            className="w-8 h-8 flex items-center justify-center bg-[#F0EDE5] rounded-lg text-[#333E50] hover:bg-[#E4E0D5] transition-colors border border-[#D1CDC2]"
          >
            <RotateCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {/* Search Bar (Stitch Screen 12ee7aa2ba624f5d914146be76b8f3ef) */}
        <div className="sticky top-14 z-30 bg-[#F9F7F2]/95 backdrop-blur-md pb-2 pt-1">
          <div className="relative flex items-center">
            <Search className="w-4 h-4 absolute left-3 text-[#75777D]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search product, brand, manufacturer or ID..."
              className="w-full h-11 pl-9 pr-4 bg-white border border-[#D1CDC2] rounded-lg text-xs font-mono text-[#1A1C1E] placeholder:text-[#75777D] focus:outline-none focus:border-[#333E50] shadow-2xs transition-all"
            />
          </div>
        </div>

        {/* Horizontal Filter Chips (Stitch Design) */}
        <div className="flex gap-1.5 overflow-x-auto no-scrollbar py-2 -mx-4 px-4">
          <button
            type="button"
            onClick={() => setActiveChip("all")}
            className={`px-3 py-1.5 rounded-full text-xs font-mono font-medium whitespace-nowrap transition-colors shadow-2xs ${
              activeChip === "all"
                ? "bg-[#333E50] text-white"
                : "bg-[#F0EDE5] text-[#4A5568] hover:bg-[#E4E0D5]"
            }`}
          >
            All ({totalCount})
          </button>

          <button
            type="button"
            onClick={() => setActiveChip("violations")}
            className={`px-3 py-1.5 rounded-full text-xs font-mono font-medium whitespace-nowrap transition-colors shadow-2xs flex items-center gap-1.5 ${
              activeChip === "violations"
                ? "bg-[#BA1A1A] text-white"
                : "bg-[#F0EDE5] text-[#4A5568] hover:bg-[#E4E0D5]"
            }`}
          >
            <AlertTriangle className="w-3 h-3" />
            <span>Violations Only</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveChip("offline")}
            className={`px-3 py-1.5 rounded-full text-xs font-mono font-medium whitespace-nowrap transition-colors shadow-2xs flex items-center gap-1.5 ${
              activeChip === "offline"
                ? "bg-[#4A5568] text-white"
                : "bg-[#F0EDE5] text-[#4A5568] hover:bg-[#E4E0D5]"
            }`}
          >
            <CloudUpload className="w-3 h-3" />
            <span>Offline Queue ({pendingCount})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveChip("packaged_food")}
            className={`px-3 py-1.5 rounded-full text-xs font-mono font-medium whitespace-nowrap transition-colors shadow-2xs ${
              activeChip === "packaged_food"
                ? "bg-[#333E50] text-white"
                : "bg-[#F0EDE5] text-[#4A5568] hover:bg-[#E4E0D5]"
            }`}
          >
            Packaged Food
          </button>

          <button
            type="button"
            onClick={() => setActiveChip("today")}
            className={`px-3 py-1.5 rounded-full text-xs font-mono font-medium whitespace-nowrap transition-colors shadow-2xs ${
              activeChip === "today"
                ? "bg-[#333E50] text-white"
                : "bg-[#F0EDE5] text-[#4A5568] hover:bg-[#E4E0D5]"
            }`}
          >
            Today
          </button>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="p-3 my-2 bg-[#FFDAD6] border-l-4 border-[#BA1A1A] rounded-r text-xs text-[#93000a]">
            {errorMessage}
          </div>
        )}

        {/* Inspection Card Feed */}
        <div className="flex flex-col gap-2.5 mt-2">
          {isLoading && inspections.length === 0 ? (
            <div className="py-12 flex flex-col items-center justify-center text-[#75777D]">
              <div className="w-8 h-8 border-2 border-[#333E50]/30 border-t-[#333E50] rounded-full animate-spin mb-2" />
              <span className="font-mono text-xs">LOADING ARCHIVE...</span>
            </div>
          ) : inspections.length === 0 ? (
            <div className="py-12 px-4 bg-white rounded-xl border border-[#D1CDC2] text-center">
              <Filter className="w-8 h-8 text-[#75777D] mx-auto mb-2 opacity-50" />
              <h3 className="text-sm font-bold text-[#1A1C1E]">No Inspections Found</h3>
              <p className="text-xs text-[#75777D] mt-1">
                No inspection records match the selected filters or search query.
              </p>
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setActiveChip("all");
                }}
                className="mt-3 px-3 py-1.5 bg-[#333E50] text-white rounded text-xs font-mono font-bold hover:bg-[#4A5568] transition"
              >
                Reset Filters
              </button>
            </div>
          ) : (
            inspections.map((insp) => {
              const hasViolations = insp.violations_count > 0;
              const isCompliant = !hasViolations && insp.status === "completed";
              const isNeedsReview = insp.status === "needs_review";

              const formattedDate = new Date(insp.created_at).toLocaleDateString("en-IN", {
                day: "2-digit",
                month: "short",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              });

              return (
                <div
                  key={insp.id}
                  className="group relative bg-white rounded-xl p-3.5 border border-[#D1CDC2] hover:border-[#333E50] transition-all shadow-2xs"
                >
                  <div className="flex items-start gap-3">
                    {/* Thumbnail */}
                    <div className="w-20 h-20 rounded-lg bg-[#F0EDE5] border border-[#D1CDC2]/60 overflow-hidden shrink-0 relative flex items-center justify-center">
                      {insp.thumbnail_url ? (
                        <img
                          src={insp.thumbnail_url}
                          alt="Package PDP"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <Camera className="w-6 h-6 text-[#75777D] opacity-40" />
                      )}
                      <div className="absolute inset-0 bg-[#333E50]/5 pointer-events-none" />
                    </div>

                    {/* Metadata & Actions */}
                    <div className="flex-1 min-w-0">
                      {/* ID and Status Badges */}
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-mono text-[10px] text-[#75777D] uppercase tracking-wider font-semibold truncate">
                          {insp.id.substring(0, 16)}...
                        </span>

                        <div className="flex items-center gap-1 shrink-0">
                          {hasViolations ? (
                            <span className="px-1.5 py-0.5 bg-[#FFDAD6] text-[#93000a] rounded font-mono text-[10px] font-bold">
                              {insp.violations_count} VIOLATION{insp.violations_count > 1 ? "S" : ""}
                            </span>
                          ) : isCompliant ? (
                            <span className="px-1.5 py-0.5 bg-[#D6E3D3] text-[#3E4A3E] rounded font-mono text-[10px] font-bold">
                              COMPLIANT
                            </span>
                          ) : isNeedsReview ? (
                            <span className="px-1.5 py-0.5 bg-[#DFC6A0] text-[#4B3B1F] rounded font-mono text-[10px] font-bold">
                              REVIEW
                            </span>
                          ) : null}

                          {insp.captured_offline ? (
                            <span className="px-1.5 py-0.5 bg-[#F0EDE5] text-[#4A5568] rounded font-mono text-[10px]">
                              OFFLINE
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 bg-[#D6E3D3] text-[#3E4A3E] rounded font-mono text-[10px]">
                              SYNCED
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Product Category / Title */}
                      <h3 className="font-semibold text-sm text-[#1A1C1E] truncate">
                        {insp.commodity_category
                          ? insp.commodity_category.toUpperCase().replace("_", " ")
                          : "PACKAGED COMMODITY"}
                      </h3>

                      {/* Region & Officer info */}
                      <p className="text-xs text-[#75777D] truncate mb-2 font-mono">
                        {insp.region || "All Regions"} · {insp.officer_name || "Assigned Officer"}
                      </p>

                      {/* Card Footer: Date + View Evidence Link */}
                      <div className="flex items-center justify-between pt-2 border-t border-[#F0EDE5]">
                        <span className="font-mono text-[10px] text-[#75777D]">
                          {formattedDate}
                        </span>

                        <Link
                          href={`/inspections/${insp.id}/evidence`}
                          className="font-mono text-xs font-bold text-[#333E50] hover:text-[#4A5568] flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform"
                        >
                          <span>View Evidence</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Offline Sync Manager Box (Stitch Design) */}
        {pendingCount > 0 && (
          <div className="mt-4 p-3.5 bg-[#F0EDE5] border border-[#D1CDC2] rounded-xl flex items-center justify-between shadow-2xs">
            <div className="flex items-center gap-2.5">
              <CloudUpload className="w-5 h-5 text-[#333E50]" />
              <div>
                <p className="font-bold text-xs text-[#1A1C1E]">Offline Sync Manager</p>
                <p className="text-[11px] text-[#75777D] font-mono">
                  {pendingCount} inspection{pendingCount > 1 ? "s" : ""} waiting for cellular uplink
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => syncNow()}
              disabled={isSyncing || !isOnline}
              className="px-3 py-1.5 bg-[#333E50] hover:bg-[#4A5568] text-white rounded font-mono text-[11px] font-bold shadow-2xs transition disabled:opacity-50"
            >
              {isSyncing ? "SYNCING..." : "SYNC NOW"}
            </button>
          </div>
        )}
      </main>

      {/* Sticky Bottom Navigation Bar (Stitch Design) */}
      <nav className="sticky bottom-0 z-40 bg-[#F9F7F2]/90 backdrop-blur-md border-t border-[#D1CDC2] px-6 py-2 flex items-center justify-around">
        <Link
          href="/"
          className="flex flex-col items-center gap-1 text-[#75777D] hover:text-[#333E50] transition"
        >
          <Camera className="w-5 h-5" />
          <span className="font-mono text-[10px] tracking-wider uppercase">Evidence</span>
        </Link>

        <Link
          href="/history"
          className="flex flex-col items-center gap-1 text-[#333E50] font-bold"
        >
          <HistoryIcon className="w-5 h-5" />
          <span className="font-mono text-[10px] tracking-wider uppercase">History</span>
        </Link>

        <button
          type="button"
          onClick={() => alert("NiyamDrishti Legal Metrology System · Rule Pack 2026.02.01 Active")}
          className="flex flex-col items-center gap-1 text-[#75777D] hover:text-[#333E50] transition"
        >
          <CheckCircle2 className="w-5 h-5" />
          <span className="font-mono text-[10px] tracking-wider uppercase">About</span>
        </button>
      </nav>
    </div>
  );
}
