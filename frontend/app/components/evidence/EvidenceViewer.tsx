"use client";
import AppLogo from "@/app/components/common/AppLogo";

import React, { useState, useRef } from "react";
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  SlidersHorizontal,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Bot,
  User as UserIcon,
  ChevronRight,
  Maximize2,
  FileCheck2,
  Camera,
  Layers,
} from "lucide-react";
import { EvidenceItem, InspectionEvidence } from "@/app/types/evidence";

interface EvidenceViewerProps {
  evidence: InspectionEvidence;
  onSelectField?: (item: EvidenceItem) => void;
  onReviewQueueClick?: () => void;
  onGenerateReportClick?: () => void;
}

export default function EvidenceViewer({
  evidence,
  onSelectField,
  onReviewQueueClick,
  onGenerateReportClick,
}: EvidenceViewerProps) {
  // Extract all distinct photo panels from explicit evidence images, items, and primary image
  const imagePanels = React.useMemo(() => {
    const panelMap = new Map<string, { id: string; url: string; label: string; count: number; role?: string }>();

    // 1. Populate from explicit evidence.images list first (all captured panels)
    if (evidence.images && evidence.images.length > 0) {
      evidence.images.forEach((img, idx) => {
        let label = `Panel ${idx + 1}`;
        const role = (img.image_role || "").toLowerCase();
        if (role.includes("front") || role.includes("pdp")) label = "Front PDP";
        else if (role.includes("back")) label = "Back Panel";
        else if (role.includes("side")) label = "Side Panel";
        else if (role.includes("sticker")) label = "Sticker";
        else if (role.includes("ecommerce")) label = "E-Commerce";

        panelMap.set(String(img.id), {
          id: String(img.id),
          url: img.storage_url,
          label,
          count: 0,
          role: img.image_role,
        });
      });
    }

    // 2. Add primary_image_url if panelMap is empty
    if (evidence.primary_image_url && panelMap.size === 0) {
      panelMap.set("front_pdp", {
        id: "front_pdp",
        url: evidence.primary_image_url,
        label: "Front PDP",
        count: 0,
        role: "front_pdp",
      });
    }

    // 3. Count declarations per panel or register item source images
    evidence.items.forEach((item, index) => {
      const imgId = String(item.source_image_id || `panel_${index}`);
      const imgUrl = item.source_image_url || evidence.primary_image_url || "";
      if (panelMap.has(imgId)) {
        panelMap.get(imgId)!.count += 1;
      } else if (imgUrl) {
        let label = `Panel ${panelMap.size + 1}`;
        const lower = imgId.toLowerCase();
        if (lower.includes("front") || lower.includes("pdp")) label = "Front PDP";
        else if (lower.includes("back")) label = "Back Panel";
        else if (lower.includes("side")) label = "Side Panel";
        else if (lower.includes("sticker")) label = "Sticker";
        panelMap.set(imgId, { id: imgId, url: imgUrl, label, count: 1 });
      }
    });

    return Array.from(panelMap.values());
  }, [evidence]);

  const [activeImageId, setActiveImageId] = useState<string>(
    imagePanels[0]?.id || "front_pdp"
  );

  // Synchronize activeImageId if imagePanels loads or updates
  React.useEffect(() => {
    if (imagePanels.length > 0 && !imagePanels.some((p) => p.id === activeImageId)) {
      setActiveImageId(imagePanels[0].id);
    }
  }, [imagePanels, activeImageId]);

  const [selectedItemId, setSelectedItemId] = useState<string>(
    evidence.items[0]?.item_id || "E01"
  );
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isContrastMode, setIsContrastMode] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const panStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const viewportRef = useRef<HTMLDivElement>(null);

  const activePanel = imagePanels.find((p) => p.id === activeImageId) || imagePanels[0];
  const activeImageUrl = activePanel?.url || evidence.primary_image_url;

  // Auto-focus zoom & pan on the selected declaration
  const focusOnItem = (item: EvidenceItem) => {
    setSelectedItemId(item.item_id);
    if (item.source_image_id && item.source_image_id !== activeImageId) {
      setActiveImageId(item.source_image_id);
    }
    if (onSelectField) onSelectField(item);

    // Center on the item's bounding box center
    const bbox = item.bounding_box;
    const centerX = bbox.left_pct + bbox.width_pct / 2;
    const centerY = bbox.top_pct + bbox.height_pct / 2;

    // Calculate translation offset so the box is centered in the viewport
    const offsetX = (50 - centerX) * 1.5;
    const offsetY = (50 - centerY) * 1.5;

    setZoom(1.35);
    setPan({ x: offsetX, y: offsetY });
  };

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.25, 3.0));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.25, 0.75));
  const handleResetZoom = () => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    panStartRef.current = { ...pan };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
    setPan({
      x: panStartRef.current.x + dx / (zoom * 2),
      y: panStartRef.current.y + dy / (zoom * 2),
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  // Touch handlers for mobile officers
  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length === 1) {
      setIsDragging(true);
      dragStartRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      panStartRef.current = { ...pan };
    }
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (!isDragging || e.touches.length !== 1) return;
    const dx = e.touches[0].clientX - dragStartRef.current.x;
    const dy = e.touches[0].clientY - dragStartRef.current.y;
    setPan({
      x: panStartRef.current.x + dx / (zoom * 2),
      y: panStartRef.current.y + dy / (zoom * 2),
    });
  };

  const handleTouchEnd = () => setIsDragging(false);

  const stats = evidence.stats || {
    total: evidence.items.length,
    passed: evidence.items.filter((i) => i.verdict === "pass").length,
    review: evidence.items.filter((i) => i.verdict === "needs_review").length,
    failed: evidence.items.filter((i) => i.verdict === "fail").length,
  };

  const passPct = stats.total > 0 ? (stats.passed / stats.total) * 100 : 0;
  const reviewPct = stats.total > 0 ? (stats.review / stats.total) * 100 : 0;
  const failPct = stats.total > 0 ? (stats.failed / stats.total) * 100 : 0;

  return (
    <div className="flex flex-col w-full bg-[#f9f9fc] text-[#1a1c1e] min-h-screen">
      {/* Header Bar */}
      <header className="sticky top-0 z-50 bg-[#f9f9fc]/90 backdrop-blur-md border-b border-[#e2e2e5] px-4 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AppLogo size={32} />
            <div className="flex flex-col">
              <span className="font-semibold text-base leading-tight tracking-tight text-[#1a1c1e]">
                NiyamDrishti
              </span>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                <span className="text-[11px] font-mono uppercase tracking-wider text-[#75777d]">
                  Inspection Mode
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-[#eeeef0] border border-[#e2e2e5] flex items-center justify-center text-[#333e50]">
              <UserIcon className="w-4 h-4" />
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto w-full pb-28">
        {/* Inspection Header Summary Section */}
        <section className="px-4 py-4 bg-[#f9f9fc] border-b border-[#e2e2e5] flex flex-col gap-2">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-xl font-bold text-[#1a1c1e] leading-snug">
                {evidence.product_name}
              </h1>
              <p className="text-xs text-[#545f72] capitalize">
                {evidence.commodity_category.replace(/_/g, " ")}
              </p>
            </div>
            {evidence.overall_status === "violations_found" && (
              <div className="bg-[#ffdad6] text-[#93000a] text-xs font-mono font-semibold px-2.5 py-1 rounded flex items-center gap-1.5 border border-red-200">
                <AlertTriangle className="w-3.5 h-3.5" />
                VIOLATIONS FOUND
              </div>
            )}
            {evidence.overall_status === "needs_review" && (
              <div className="bg-amber-100 text-amber-900 text-xs font-mono font-semibold px-2.5 py-1 rounded flex items-center gap-1.5 border border-amber-200">
                <HelpCircle className="w-3.5 h-3.5" />
                REVIEW REQUIRED
              </div>
            )}
            {evidence.overall_status === "compliant" && (
              <div className="bg-emerald-100 text-emerald-900 text-xs font-mono font-semibold px-2.5 py-1 rounded flex items-center gap-1.5 border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5" />
                COMPLIANT
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-y-2 gap-x-4 mt-2 pt-2 border-t border-[#eeeef0] text-xs">
            <div className="flex flex-col">
              <span className="font-mono text-[10px] text-[#75777d] uppercase">
                INSPECTION ID
              </span>
              <span className="font-mono text-xs font-medium text-[#1a1c1e]">
                {evidence.inspection_id.slice(0, 13)}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="font-mono text-[10px] text-[#75777d] uppercase">
                OFFICER
              </span>
              <span className="font-mono text-xs font-medium text-[#1a1c1e] truncate">
                {evidence.officer_name || "Insp. Officer"}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="font-mono text-[10px] text-[#75777d] uppercase">
                RULE PACK
              </span>
              <span className="font-mono text-xs font-medium text-[#1a1c1e]">
                v{evidence.rule_pack_version}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="font-mono text-[10px] text-[#75777d] uppercase">
                ASSIST
              </span>
              <span className="font-mono text-xs font-medium text-[#333e50] flex items-center gap-1">
                <Bot className="w-3 h-3" /> AI-Assisted
              </span>
            </div>
          </div>
        </section>

        {/* Evidence Interactive Viewport Section */}
        <section className="relative w-full bg-[#1a1c1e] border-b border-[#e2e2e5] overflow-hidden select-none">
          {/* Photo Panel / Angle Selector Bar */}
          {imagePanels.length > 1 && (
            <div className="bg-[#202224] border-b border-white/10 px-3 py-2 flex items-center justify-between gap-2 overflow-x-auto">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-amber-400 font-semibold uppercase flex items-center gap-1 shrink-0">
                  <Camera className="w-3.5 h-3.5" />
                  <span>Panels ({imagePanels.length}):</span>
                </span>
                <div className="flex items-center gap-1.5 overflow-x-auto">
                  {imagePanels.map((panel) => (
                    <button
                      key={panel.id}
                      type="button"
                      onClick={() => setActiveImageId(panel.id)}
                      className={`px-3 py-1 rounded text-xs font-mono transition-all flex items-center gap-1.5 shrink-0 ${
                        activeImageId === panel.id
                          ? "bg-amber-500 text-slate-950 font-bold shadow-sm ring-1 ring-amber-300"
                          : "bg-white/10 text-gray-200 hover:text-white hover:bg-white/20 border border-white/10"
                      }`}
                    >
                      <span>{panel.label}</span>
                      {panel.count > 0 && (
                        <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                          activeImageId === panel.id ? "bg-slate-950 text-amber-300" : "bg-white/20 text-white"
                        }`}>
                          {panel.count}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
              <span className="text-[10px] font-mono text-gray-400 shrink-0 hidden sm:inline">
                Tap panel to inspect declarations
              </span>
            </div>
          )}

          <div
            ref={viewportRef}
            className={`relative w-full h-[360px] sm:h-[420px] overflow-hidden ${
              isDragging ? "cursor-grabbing" : "cursor-grab"
            }`}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
          >
            {/* Pannable & Zoomable Canvas */}
            <div
              className="absolute inset-0 w-full h-full transition-transform duration-200 ease-out origin-center"
              style={{
                transform: `scale(${zoom}) translate(${pan.x}px, ${pan.y}px)`,
              }}
            >
              {/* Product Photo */}
              {activeImageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={activeImageUrl}
                  alt={evidence.product_name}
                  className={`w-full h-full object-contain pointer-events-none transition-all duration-300 ${
                    isContrastMode ? "grayscale contrast-200 brightness-110" : ""
                  }`}
                />
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center text-slate-400">
                  <Maximize2 className="w-12 h-12 mb-2 opacity-50" />
                  <span className="text-sm font-mono">No Image Uploaded</span>
                </div>
              )}

              {/* Bounding Box Overlays (Filtered to current active panel) */}
              <div className="absolute inset-0 w-full h-full pointer-events-none">
                {evidence.items
                  .filter(
                    (item) =>
                      !item.source_image_id ||
                      item.source_image_id === activeImageId ||
                      imagePanels.length <= 1
                  )
                  .map((item) => {
                    const isSelected = item.item_id === selectedItemId;
                  const bbox = item.bounding_box;

                  return (
                    <div
                      key={item.item_id}
                      onClick={(e) => {
                        e.stopPropagation();
                        focusOnItem(item);
                      }}
                      className={`absolute pointer-events-auto cursor-pointer transition-all duration-300 ${
                        isSelected
                          ? "border-2 border-indigo-400 bg-indigo-500/20 shadow-[0_0_12px_rgba(99,102,241,0.6)] z-20"
                          : "border border-white/60 bg-black/10 hover:border-white hover:bg-white/10 z-10"
                      }`}
                      style={{
                        top: `${bbox.top_pct}%`,
                        left: `${bbox.left_pct}%`,
                        width: `${bbox.width_pct}%`,
                        height: `${bbox.height_pct}%`,
                      }}
                    >
                      {/* Corner Accents */}
                      <div
                        className={`absolute -top-1 -left-1 w-2.5 h-2.5 border-t-2 border-l-2 ${
                          isSelected ? "border-indigo-400" : "border-white"
                        }`}
                      />
                      <div
                        className={`absolute -bottom-1 -right-1 w-2.5 h-2.5 border-b-2 border-r-2 ${
                          isSelected ? "border-indigo-400" : "border-white"
                        }`}
                      />

                      {/* Tag Label */}
                      <span
                        className={`absolute -top-5 left-0 font-mono text-[10px] px-1.5 py-0.5 rounded-sm flex items-center gap-1 shadow-sm ${
                          isSelected
                            ? "bg-indigo-600 text-white font-bold ring-1 ring-white/40"
                            : "bg-black/80 text-white"
                        }`}
                      >
                        {item.item_id}
                      </span>

                      {/* Measurement Annotation Callout for Selected Item */}
                      {isSelected && item.measured_dimension && (
                        <div className="absolute -right-24 top-1/2 -translate-y-1/2 flex items-center z-30 pointer-events-none">
                          <div className="w-4 border-b border-dashed border-indigo-400" />
                          <div className="bg-slate-900/90 backdrop-blur-md text-white border border-indigo-400/80 px-1.5 py-0.5 rounded text-[9px] font-mono shadow-md flex flex-col whitespace-nowrap">
                            {item.measured_dimension.is_calibrated ? (
                              <span className="text-indigo-300 font-bold">
                                {item.measured_dimension.height_mm}mm (CAL)
                              </span>
                            ) : (
                              <span className="text-amber-400 font-bold">
                                {((item.measured_dimension.pdp_ratio || 0) * 100).toFixed(1)}% (EST)
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Multi-Panel Quick Switcher Thumbnails */}
            {imagePanels.length > 1 && (
              <div className="absolute bottom-3 left-3 flex items-center gap-1.5 z-30 bg-black/60 backdrop-blur-md p-1 rounded-lg border border-white/15">
                {imagePanels.map((panel) => (
                  <button
                    key={panel.id}
                    type="button"
                    onClick={() => setActiveImageId(panel.id)}
                    className={`relative w-10 h-10 rounded overflow-hidden border transition-all ${
                      activeImageId === panel.id
                        ? "border-amber-400 ring-2 ring-amber-400/60 scale-105"
                        : "border-white/30 opacity-70 hover:opacity-100"
                    }`}
                    title={`Switch to ${panel.label}`}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={panel.url} alt={panel.label} className="w-full h-full object-cover" />
                    <span className="absolute bottom-0 inset-x-0 bg-black/85 text-[7px] font-mono text-white text-center truncate px-0.5 font-bold">
                      {panel.label.replace("Panel", "P")}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {/* Viewport Floating Controls */}
            <div className="absolute bottom-3 right-3 flex items-center gap-1.5 z-30">
              <button
                type="button"
                onClick={handleZoomIn}
                className="w-9 h-9 rounded-full bg-slate-900/80 backdrop-blur border border-white/20 flex items-center justify-center text-white hover:bg-slate-800 transition-colors shadow-sm"
                title="Zoom In"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={handleZoomOut}
                className="w-9 h-9 rounded-full bg-slate-900/80 backdrop-blur border border-white/20 flex items-center justify-center text-white hover:bg-slate-800 transition-colors shadow-sm"
                title="Zoom Out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={handleResetZoom}
                className="w-9 h-9 rounded-full bg-slate-900/80 backdrop-blur border border-white/20 flex items-center justify-center text-white hover:bg-slate-800 transition-colors shadow-sm"
                title="Reset Zoom"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setIsContrastMode(!isContrastMode)}
                className={`w-9 h-9 rounded-full backdrop-blur border flex items-center justify-center transition-colors shadow-sm ${
                  isContrastMode
                    ? "bg-amber-500 border-amber-300 text-slate-950 font-bold"
                    : "bg-slate-900/80 border-white/20 text-white hover:bg-slate-800"
                }`}
                title="Toggle High-Contrast B&W Mode"
              >
                <SlidersHorizontal className="w-4 h-4" />
              </button>
            </div>
          </div>
        </section>

        {/* Declarations Progress Breakdown */}
        <section className="px-4 py-4 bg-[#f9f9fc] border-b border-[#e2e2e5]">
          <div className="flex justify-between items-end mb-2">
            <h2 className="text-base font-semibold text-[#1a1c1e]">
              Declarations
            </h2>
            <span className="font-mono text-xs text-[#75777d]">
              {stats.total} CHECKED
            </span>
          </div>

          {/* Tri-Color Progress Bar */}
          <div className="w-full h-2.5 bg-[#e2e2e5] rounded-full overflow-hidden flex shadow-inner">
            <div
              className="h-full bg-emerald-500 transition-all duration-500 ease-out"
              style={{ width: `${passPct}%` }}
              title={`${stats.passed} PASS`}
            />
            <div
              className="h-full bg-amber-400 transition-all duration-500 ease-out"
              style={{ width: `${reviewPct}%` }}
              title={`${stats.review} REVIEW`}
            />
            <div
              className="h-full bg-red-500 transition-all duration-500 ease-out"
              style={{ width: `${failPct}%` }}
              title={`${stats.failed} FAIL`}
            />
          </div>

          <div className="flex justify-between mt-1.5 font-mono text-[11px]">
            <span className="text-emerald-700 font-medium">
              {stats.passed} PASS
            </span>
            <span className="text-amber-800 font-medium">
              {stats.review} REVIEW
            </span>
            <span className="text-red-700 font-medium">
              {stats.failed} FAIL
            </span>
          </div>
        </section>

        {/* Declaration Register List */}
        <section className="flex flex-col bg-white divide-y divide-[#eeeef0] border-b border-[#e2e2e5]">
          {evidence.items.map((item) => {
            const isSelected = item.item_id === selectedItemId;

            return (
              <div
                key={item.item_id}
                onClick={() => focusOnItem(item)}
                className={`flex items-center justify-between p-4 cursor-pointer transition-colors min-h-[56px] ${
                  isSelected
                    ? "border-l-4 border-l-[#333e50] bg-slate-50/90 shadow-sm"
                    : "hover:bg-slate-50/60 active:bg-slate-100"
                }`}
              >
                <div className="flex flex-col gap-1 flex-1 min-w-0 pr-4">
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-mono text-[11px] font-bold w-7 ${
                        isSelected ? "text-[#333e50]" : "text-[#75777d]"
                      }`}
                    >
                      {item.item_id}
                    </span>
                    <span className="text-sm font-semibold text-[#1a1c1e] truncate uppercase">
                      {item.field_label}
                    </span>
                    {item.source_image_id && (
                      <span className="text-[9px] font-mono font-medium px-1.5 py-0.5 rounded bg-[#e8eef6] text-[#2c3e50] uppercase border border-[#c4d6eb]">
                        {item.source_image_id.includes("front") || item.source_image_id.includes("pdp")
                          ? "Front PDP"
                          : item.source_image_id.includes("back")
                          ? "Back Panel"
                          : item.source_image_id.includes("side")
                          ? "Side Panel"
                          : item.source_image_id.includes("sticker")
                          ? "Sticker"
                          : "Panel"}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 pl-9 text-xs">
                    <span className="font-mono text-[#333e50] font-medium truncate">
                      {item.parsed_value || item.raw_text || "—"}
                    </span>
                    <span className="text-[10px] font-mono text-[#75777d] bg-[#eeeef0] px-1.5 py-0.5 rounded">
                      {Math.round(item.confidence * 100)}%
                    </span>
                    {item.measured_dimension && (
                      <span className="text-[10px] font-mono text-indigo-700 bg-indigo-50 border border-indigo-100 px-1 py-0.5 rounded">
                        {item.measured_dimension.is_calibrated
                          ? `${item.measured_dimension.height_mm}mm`
                          : "Uncalibrated"}
                      </span>
                    )}
                  </div>

                  {/* Violation details or Warning remarks */}
                  {item.violations.length > 0 && (
                    <div className="pl-9 mt-1">
                      {item.violations.map((v, i) => (
                        <p
                          key={i}
                          className="text-[11px] font-mono text-red-600 leading-tight"
                        >
                          • {v.description}
                        </p>
                      ))}
                    </div>
                  )}
                  {item.measured_dimension?.warning && (
                    <p className="pl-9 text-[11px] font-mono text-amber-700 leading-tight mt-0.5">
                      • {item.measured_dimension.warning}
                    </p>
                  )}
                </div>

                {/* Verdict Badge */}
                <div className="flex items-center gap-2">
                  {item.verdict === "pass" && (
                    <span className="bg-emerald-100 text-emerald-800 font-mono text-[11px] font-bold px-2.5 py-1 rounded">
                      PASS
                    </span>
                  )}
                  {item.verdict === "needs_review" && (
                    <span className="bg-amber-100 text-amber-800 font-mono text-[11px] font-bold px-2.5 py-1 rounded border border-amber-300 flex items-center gap-1">
                      <HelpCircle className="w-3 h-3" /> REVIEW
                    </span>
                  )}
                  {item.verdict === "fail" && (
                    <span className="bg-red-100 text-red-800 font-mono text-[11px] font-bold px-2.5 py-1 rounded border border-red-300 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> FAIL
                    </span>
                  )}
                  <ChevronRight className="w-4 h-4 text-[#75777d]" />
                </div>
              </div>
            );
          })}
        </section>
      </main>

      {/* Floating Action Footer */}
      <footer className="fixed bottom-0 left-0 right-0 z-40 bg-[#f9f9fc]/90 backdrop-blur-md border-t border-[#e2e2e5] p-3 shadow-lg">
        <div className="max-w-4xl mx-auto flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={onReviewQueueClick}
            className="flex-1 bg-white border border-[#75777d]/30 text-[#333e50] hover:bg-slate-50 font-semibold text-xs py-2.5 px-4 rounded-md transition-colors flex items-center justify-center gap-1.5 shadow-sm"
          >
            <HelpCircle className="w-4 h-4 text-amber-600" />
            Review Queue
          </button>
          <button
            type="button"
            onClick={onGenerateReportClick}
            className="flex-1 bg-[#333e50] hover:bg-[#27303e] text-white font-semibold text-xs py-2.5 px-4 rounded-md transition-colors flex items-center justify-center gap-1.5 shadow-sm"
          >
            <FileCheck2 className="w-4 h-4" />
            Generate Report
          </button>
        </div>
      </footer>
    </div>
  );
}
