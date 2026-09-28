"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Barcode,
  ArrowLeft,
  ChevronRight,
  CloudUpload,
  History,
  Image as ImageIcon,
  Info,
  Loader2,
  ScanLine,
  Settings,
  User,
  Wifi,
  WifiOff,
} from "lucide-react";
import AppLogo from "@/app/components/common/AppLogo";
import { OfflineImage, OfflineLocalEvidence } from "@/app/db/dexie";

type LocalEvidenceItem = {
  id: string;
  kind: "ocr" | "barcode";
  imageId: string;
  imageRole: string;
  text: string;
  detail?: string;
  box: { x: number; y: number; w: number; h: number };
};

interface LocalProvisionalEvidenceViewerProps {
  inspectionId: string;
  officerName?: string;
  capturedAt: string;
  images: OfflineImage[];
  evidence: OfflineLocalEvidence;
  isSyncing: boolean;
  syncError: string | null;
  onSyncNow: () => void;
  onBack: () => void;
}

function panelLabel(role: string): string {
  return {
    front_pdp: "FRONT PDP",
    back_panel: "BACK / SIDE",
    side_panel: "BACK / SIDE",
    sticker: "STICKER",
    ecommerce_listing: "E-COM LISTING",
  }[role] || role.replace(/_/g, " ").toUpperCase();
}

function formatCaptureTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : new Intl.DateTimeFormat("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
}

/**
 * Approved Stitch state: evidence from an offline Android scan is deliberately
 * presented as raw local observations, not declaration findings or compliance.
 */
export default function LocalProvisionalEvidenceViewer({
  inspectionId,
  officerName,
  capturedAt,
  images,
  evidence,
  isSyncing,
  syncError,
  onSyncNow,
  onBack,
}: LocalProvisionalEvidenceViewerProps) {
  const [activeImageId, setActiveImageId] = useState(images[0]?.id || "");
  const [activeItemId, setActiveItemId] = useState<string | null>(null);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [viewportSize, setViewportSize] = useState({ width: 0, height: 0 });
  const [isOnline, setIsOnline] = useState(false);
  const viewportRef = useRef<HTMLDivElement>(null);

  const items = useMemo<LocalEvidenceItem[]>(() => {
    const evidenceByImage = new Map(evidence.images.map((entry) => [entry.imageId, entry]));
    const result: LocalEvidenceItem[] = [];
    images.forEach((image) => {
      const local = evidenceByImage.get(image.id);
      if (!local) return;
      local.ocrLines.forEach((line, index) => {
        result.push({
          id: `ocr-${image.id}-${index}`,
          kind: "ocr",
          imageId: image.id,
          imageRole: image.imageRole,
          text: line.text,
          detail: "RAW OCR · ON-DEVICE",
          box: line.boundingBox,
        });
      });
      local.barcodes.forEach((barcode, index) => {
        result.push({
          id: `barcode-${image.id}-${index}`,
          kind: "barcode",
          imageId: image.id,
          imageRole: image.imageRole,
          text: barcode.rawValue,
          detail: `BARCODE DETECTED LOCALLY · FORMAT ${barcode.format}`,
          box: barcode.boundingBox,
        });
      });
    });
    return result;
  }, [evidence.images, images]);

  const resolvedActiveImageId = activeImageId || images[0]?.id || "";
  const activeImage = images.find((image) => image.id === resolvedActiveImageId) || images[0];
  const activeEvidence = evidence.images.find((item) => item.imageId === activeImage?.id);
  const activeItems = items.filter((item) => item.imageId === activeImage?.id);
  const activeItem = items.find((item) => item.id === activeItemId) || null;

  useEffect(() => {
    const updateNetworkState = () => setIsOnline(navigator.onLine);
    updateNetworkState();
    window.addEventListener("online", updateNetworkState);
    window.addEventListener("offline", updateNetworkState);
    return () => {
      window.removeEventListener("online", updateNetworkState);
      window.removeEventListener("offline", updateNetworkState);
    };
  }, []);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const update = () => setViewportSize({ width: viewport.clientWidth, height: viewport.clientHeight });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(viewport);
    return () => observer.disconnect();
  }, []);

  const displayedRect = useMemo(() => {
    if (!imageSize.width || !imageSize.height || !viewportSize.width || !viewportSize.height) return null;
    const scale = Math.min(viewportSize.width / imageSize.width, viewportSize.height / imageSize.height);
    const width = imageSize.width * scale;
    const height = imageSize.height * scale;
    return { left: (viewportSize.width - width) / 2, top: (viewportSize.height - height) / 2, width, height };
  }, [imageSize, viewportSize]);

  const selectItem = (item: LocalEvidenceItem) => {
    setActiveImageId(item.imageId);
    setActiveItemId(item.id);
  };

  return (
    <div className="min-h-screen bg-[#F9F7F2] text-[#1A1C1E] pb-20">
      <header className="sticky top-0 z-30 border-b border-[#D1CDC2] bg-[#F9F7F2]/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-md items-center justify-between">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={onBack}
              className="p-1.5 rounded-full hover:bg-black/5 active:scale-95 text-[#333E50]"
              aria-label="Go Back"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <AppLogo size={32} />
            <div>
              <p className="text-base font-semibold leading-tight">NiyamDrishti</p>
              <p className="font-mono-data text-[10px] tracking-[0.13em] text-[#566155]">EVIDENCE SYSTEM</p>
            </div>
          </div>
          <div className={`flex items-center gap-1 rounded-full px-3 py-1 font-mono-data text-[10px] font-bold tracking-wide ${
            isOnline ? "bg-[#D6E3D3] text-[#3E4A3E]" : "bg-[#FFDAD6] text-[#93000A]"
          }`}>
            {isOnline ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
            {isOnline ? "ONLINE" : "OFFLINE"}
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#333E50] text-white">
            <User className="h-4 w-4" />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-md">
        <section className="border-b border-[#D1CDC2] px-4 py-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-bold">LOCAL PROVISIONAL EVIDENCE</h1>
              <p className="mt-1 font-mono-data text-[11px] font-semibold tracking-wide text-[#8A6415]">
                {isOnline ? "PENDING MANUAL SYNC" : "OFFLINE / PENDING MANUAL SYNC"}
              </p>
            </div>
            <button
              type="button"
              onClick={onSyncNow}
              disabled={isSyncing}
              className="flex min-h-10 shrink-0 items-center gap-1.5 rounded bg-[#4A5568] px-3 text-xs font-bold text-white disabled:opacity-60"
            >
              {isSyncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CloudUpload className="h-4 w-4" />}
              {isSyncing ? "SYNCING" : "SYNC NOW"}
            </button>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-[#E1DDD3] pt-3 font-mono-data text-[10px]">
            <div><dt className="text-[#75777D]">INSPECTION ID</dt><dd className="mt-0.5 truncate text-xs">{inspectionId}</dd></div>
            <div><dt className="text-[#75777D]">CAPTURE TIME</dt><dd className="mt-0.5 text-xs">{formatCaptureTime(capturedAt)}</dd></div>
            <div><dt className="text-[#75777D]">OFFICER</dt><dd className="mt-0.5 text-xs">{officerName || "Local officer session"}</dd></div>
            <div><dt className="text-[#75777D]">ENGINE</dt><dd className="mt-0.5 text-xs">ML KIT OCR + BARCODE</dd></div>
          </dl>
          <div className="mt-3 flex gap-2 border-l-2 border-[#B98C32] bg-[#F3E8C8] px-3 py-2 text-xs leading-5 text-[#58420E]">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <p>Raw evidence only — final compliance verification requires sync. Evidence is stored on this device.</p>
          </div>
        </section>

        <section className="border-b border-[#D1CDC2] bg-[#333E50] px-4 py-3 text-white">
          <p className="font-mono-data text-[10px] tracking-[0.15em] text-[#D8E3FA]">ACTIVE ANNOTATION CANVAS · {panelLabel(activeImage?.imageRole || "")}</p>
          <div ref={viewportRef} className="relative mt-3 h-[420px] overflow-hidden bg-[#20262F]">
            {activeImage ? (
              <>
                <img
                  src={activeImage.dataUrl}
                  alt={`${panelLabel(activeImage.imageRole)} local evidence`}
                  className="h-full w-full object-contain"
                  onLoad={(event) => setImageSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })}
                />
                {displayedRect && activeItems.map((item, index) => {
                  const selected = item.id === activeItem?.id;
                  const left = displayedRect.left + (item.box.x / imageSize.width) * displayedRect.width;
                  const top = displayedRect.top + (item.box.y / imageSize.height) * displayedRect.height;
                  const width = (item.box.w / imageSize.width) * displayedRect.width;
                  const height = (item.box.h / imageSize.height) * displayedRect.height;
                  const marker = item.kind === "barcode" ? `B${String(index + 1).padStart(2, "0")}` : `E${String(index + 1).padStart(2, "0")}`;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => selectItem(item)}
                      className={`absolute border-2 text-left transition-opacity ${selected ? "z-10 border-[#D6E3D3] opacity-100" : "border-[#AFC7E8] opacity-80"}`}
                      style={{ left, top, width: Math.max(width, 4), height: Math.max(height, 4) }}
                      aria-label={`Select ${item.kind} evidence ${marker}`}
                    >
                      <span className={`absolute -top-5 left-0 whitespace-nowrap px-1.5 py-0.5 font-mono-data text-[9px] font-bold ${item.kind === "barcode" ? "bg-[#5F7C63] text-white" : "bg-[#4A6B94] text-white"}`}>{marker} · {item.kind === "barcode" ? "BARCODE" : "OCR"}</span>
                    </button>
                  );
                })}
              </>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-[#D8E3FA]">No saved source image</div>
            )}
          </div>
          <p className="mt-2 flex items-center gap-1.5 font-mono-data text-[10px] text-[#D8E3FA]"><ScanLine className="h-3.5 w-3.5" /> Tap bounding boxes to inspect local extractions</p>
        </section>

        <section className="border-b border-[#D1CDC2] px-4 py-3">
          <p className="font-mono-data text-[10px] tracking-[0.14em] text-[#566155]">SOURCE IMAGE NAVIGATOR</p>
          <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
            {images.map((image, index) => (
              <button key={image.id} type="button" onClick={() => { setActiveImageId(image.id); setActiveItemId(null); }} className={`flex w-24 shrink-0 flex-col gap-1 rounded border p-1.5 text-left ${image.id === activeImage?.id ? "border-2 border-[#4A5568] bg-white" : "border-[#D1CDC2] bg-[#F0EDE5]"}`}>
                <img src={image.dataUrl} alt={panelLabel(image.imageRole)} className="h-12 w-full object-cover" />
                <span className="font-mono-data text-[9px] font-bold">{String(index + 1).padStart(2, "0")} {panelLabel(image.imageRole)}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="px-4 py-4">
          <div className="flex items-center justify-between border-b border-[#D1CDC2] pb-2">
            <p className="font-mono-data text-[11px] font-bold tracking-[0.13em] text-[#566155]">LOCAL EVIDENCE REGISTER</p>
            <span className="font-mono-data text-[10px] text-[#75777D]">{items.length} ITEMS</span>
          </div>
          <div className="divide-y divide-[#E1DDD3]">
            {items.map((item, index) => {
              const marker = item.kind === "barcode" ? `B${String(index + 1).padStart(2, "0")}` : `E${String(index + 1).padStart(2, "0")}`;
              const selected = item.id === activeItem?.id;
              return (
                <button key={item.id} type="button" onClick={() => selectItem(item)} className={`flex w-full gap-3 py-3 text-left ${selected ? "bg-[#EEF2F7]" : ""}`}>
                  <div className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center ${item.kind === "barcode" ? "bg-[#D6E3D3] text-[#3E4A3E]" : "bg-[#D8E3FA] text-[#333E50]"}`}>
                    {item.kind === "barcode" ? <Barcode className="h-4 w-4" /> : <ScanLine className="h-4 w-4" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-mono-data text-[10px] font-bold text-[#566155]">{marker} · {item.detail}</p>
                    <p className="mt-1 break-words text-sm font-semibold">{item.text}</p>
                    <p className="mt-1 font-mono-data text-[10px] text-[#75777D]">{panelLabel(item.imageRole)} · Awaiting server verification</p>
                  </div>
                  <ChevronRight className="mt-3 h-4 w-4 shrink-0 text-[#75777D]" />
                </button>
              );
            })}
          </div>

          {items.length === 0 && (
            <div className="py-5 text-center text-sm text-[#566155]">No readable local OCR or barcode evidence was found in these images.</div>
          )}
          {(syncError || evidence.status === "partial" || activeEvidence?.ocrError || activeEvidence?.barcodeError) && (
            <div className="mt-3 flex gap-2 border-l-2 border-[#B98C32] bg-[#F3E8C8] px-3 py-2 text-xs text-[#58420E]">
              <Info className="h-4 w-4 shrink-0" />
              <p>{syncError || activeEvidence?.ocrError || activeEvidence?.barcodeError || "Some text could not be read locally. Final verification is pending sync."}</p>
            </div>
          )}
        </section>
      </main>

      <nav className="fixed bottom-0 left-0 right-0 border-t border-[#D1CDC2] bg-[#F9F7F2]/95 px-6 py-2 backdrop-blur">
        <div className="mx-auto flex max-w-md items-center justify-around">
          <div className="flex flex-col items-center gap-1 text-[#333E50]"><ImageIcon className="h-5 w-5" /><span className="font-mono-data text-[9px] font-bold">EVIDENCE</span></div>
          <Link href="/history" className="flex flex-col items-center gap-1 text-[#75777D]"><History className="h-5 w-5" /><span className="font-mono-data text-[9px]">HISTORY</span></Link>
          <Link href="/" className="flex flex-col items-center gap-1 text-[#75777D]"><Settings className="h-5 w-5" /><span className="font-mono-data text-[9px]">SETTINGS</span></Link>
        </div>
      </nav>
    </div>
  );
}
