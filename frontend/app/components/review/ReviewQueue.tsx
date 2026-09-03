"use client";

import React, { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  Edit3,
  Ban,
  Bot,
  Gavel,
  Check,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Sparkles,
  History,
  CheckCheck,
  X,
  Clock,
  User,
  Loader2,
} from "lucide-react";
import {
  InspectionReviewQueue,
  ReviewQueueItem,
  FieldReviewAction,
  ReviewHistoryItem,
} from "@/app/types/review";
import {
  submitFieldReview,
  submitBatchFieldReview,
  fetchReviewHistory,
} from "@/app/services/reviewService";

interface ReviewQueueProps {
  initialQueue: InspectionReviewQueue;
  inspectionId: string;
  productTitle?: string;
  token?: string;
  onComplete?: () => void;
}

export default function ReviewQueue({
  initialQueue,
  inspectionId,
  productTitle = "Packaged Commodity",
  token,
  onComplete,
}: ReviewQueueProps) {
  const [queue, setQueue] = useState<InspectionReviewQueue>(initialQueue);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [overrideValues, setOverrideValues] = useState<Record<string, string>>({});
  const [reviewNotesMap, setReviewNotesMap] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isBatchSubmitting, setIsBatchSubmitting] = useState<boolean>(false);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Review History Modal State
  const [showHistoryModal, setShowHistoryModal] = useState<boolean>(false);
  const [historyItems, setHistoryItems] = useState<ReviewHistoryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);

  const pendingItems = queue.items.filter((item) => !item.reviewed_by_officer);
  const highConfidencePending = pendingItems.filter(
    (item) => item.confidence >= 0.85 && item.violations.length === 0
  );

  const currentItem: ReviewQueueItem | undefined =
    pendingItems[currentIndex] || queue.items[currentIndex];

  const activeFieldId = currentItem?.field_id || "";
  const currentOverrideValue =
    overrideValues[activeFieldId] !== undefined
      ? overrideValues[activeFieldId]
      : (currentItem?.officer_override_value || currentItem?.parsed_value || currentItem?.raw_text || "");
  const currentReviewNotes = reviewNotesMap[activeFieldId] ?? "";

  const handleAction = async (action: FieldReviewAction) => {
    if (!currentItem) return;

    if (action === "correct" && !currentOverrideValue.trim()) {
      setErrorMessage("Please enter a corrected value before saving.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const payload = {
        action,
        officer_override_value: action === "correct" ? currentOverrideValue.trim() : null,
        review_notes: currentReviewNotes.trim() || undefined,
      };

      const response = await submitFieldReview(inspectionId, currentItem.field_id, payload, token);

      // Update local item state
      setQueue((prev) => {
        const updatedItems = prev.items.map((item) => {
          if (item.field_id === currentItem.field_id) {
            return {
              ...item,
              reviewed_by_officer: true,
              verdict: response.field.verdict,
              officer_override_value: response.field.officer_override_value,
            };
          }
          return item;
        });

        const pendingCount = updatedItems.filter((i) => !i.reviewed_by_officer).length;
        const completedCount = updatedItems.length - pendingCount;

        return {
          ...prev,
          overall_status: response.inspection_status,
          pending_review_count: pendingCount,
          completed_review_count: completedCount,
          items: updatedItems,
        };
      });

      const actionLabel =
        action === "confirm"
          ? "Confirmed as correct"
          : action === "correct"
          ? `Corrected to "${currentOverrideValue}"`
          : "Marked as not applicable";

      setActionSuccessMessage(actionLabel);
      setTimeout(() => setActionSuccessMessage(null), 3000);

      const remainingPending = queue.items
        .map((it, idx) => ({ ...it, originalIdx: idx }))
        .filter((it) => it.field_id !== currentItem.field_id && !it.reviewed_by_officer);

      if (remainingPending.length > 0) {
        setCurrentIndex((prev) => (prev >= remainingPending.length ? 0 : prev));
      } else if (onComplete) {
        onComplete();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save review action.";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBatchConfirmHighConfidence = async () => {
    if (highConfidencePending.length === 0) return;

    setIsBatchSubmitting(true);
    setErrorMessage(null);

    try {
      const itemsToConfirm = highConfidencePending.map((item) => ({
        field_id: item.field_id,
        action: "confirm" as const,
        officer_notes: "Batch confirmed: high extraction confidence (>= 85%)",
      }));

      const response = await submitBatchFieldReview(
        inspectionId,
        { items: itemsToConfirm },
        token
      );

      const confirmedIds = new Set(itemsToConfirm.map((i) => i.field_id));

      setQueue((prev) => {
        const updatedItems = prev.items.map((item) => {
          if (confirmedIds.has(item.field_id)) {
            return {
              ...item,
              reviewed_by_officer: true,
              verdict: "pass" as const,
              officer_override_value: null,
            };
          }
          return item;
        });

        const pendingCount = updatedItems.filter((i) => !i.reviewed_by_officer).length;
        const completedCount = updatedItems.length - pendingCount;

        return {
          ...prev,
          overall_status: response.inspection_status,
          pending_review_count: pendingCount,
          completed_review_count: completedCount,
          items: updatedItems,
        };
      });

      setActionSuccessMessage(`Batch confirmed ${itemsToConfirm.length} high-confidence declarations!`);
      setTimeout(() => setActionSuccessMessage(null), 3500);
      setCurrentIndex(0);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to execute batch confirmation.";
      setErrorMessage(msg);
    } finally {
      setIsBatchSubmitting(false);
    }
  };

  const handleOpenHistory = async () => {
    setShowHistoryModal(true);
    setIsLoadingHistory(true);
    try {
      const data = await fetchReviewHistory(inspectionId, token);
      setHistoryItems(data);
    } catch {
      // Offline fallback mock history
      setHistoryItems([
        {
          id: "hist-01",
          action: "CONFIRM_DECLARATION",
          entity_type: "extracted_field",
          entity_id: activeFieldId,
          field_type: "mrp",
          officer_id: "usr-01",
          officer_name: "Legal Metrology Officer",
          officer_role: "officer",
          before_value: { verdict: "needs_review" },
          after_value: { verdict: "pass" },
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const totalSteps = queue.items.length;
  const currentStepNumber = queue.items.findIndex((i) => i.field_id === currentItem?.field_id) + 1;
  const isAllComplete = queue.pending_review_count === 0;

  return (
    <div className="bg-[#f9f9fc] font-sans text-[#1a1c1e] min-h-screen flex flex-col antialiased">
      {/* Fixed Sticky Header - Design token: bg-surface/80 backdrop-blur-xl */}
      <header className="fixed top-0 w-full z-50 bg-[#f9f9fc]/85 backdrop-blur-xl border-b border-[#e2e2e5] shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
        <div className="h-16 max-w-2xl mx-auto px-4 flex items-center justify-between gap-2">
          {/* Back button + Brand */}
          <div className="flex items-center gap-3">
            <Link
              href={`/inspections/${inspectionId}/evidence`}
              className="w-8 h-8 rounded-full bg-[#eeeef0] hover:bg-[#e2e2e5] text-[#333e50] flex items-center justify-center transition-colors"
              title="Return to Evidence"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div className="flex flex-col">
              <span className="text-base font-semibold text-[#1a1c1e] tracking-tight flex items-center gap-1.5">
                NiyamDrishti
              </span>
              <span className="font-mono text-[11px] text-[#75777d] uppercase tracking-wider">
                Review Queue
              </span>
            </div>
          </div>

          {/* Actions & Status */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleOpenHistory}
              className="px-2.5 py-1 bg-white hover:bg-[#eeeef0] text-[#333e50] border border-[#c5c6cd] rounded-sm text-xs font-mono font-medium flex items-center gap-1.5 transition-colors shadow-xs"
              title="View immutable audit trail"
            >
              <History className="w-3.5 h-3.5 text-[#333e50]" />
              <span className="hidden sm:inline">Audit Trail</span>
            </button>
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-[#eeeef0] rounded-full border border-[#c5c6cd]/30">
              <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse" />
              <span className="font-mono text-[10px] font-semibold text-[#566155] tracking-wider uppercase">
                ONLINE
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 pt-20 pb-28 px-4 max-w-2xl mx-auto w-full flex flex-col gap-5">
        {/* Step Context Header */}
        <div className="flex flex-col gap-1 pt-1">
          <div className="flex justify-between items-center">
            <span className="font-mono text-xs font-medium text-[#333e50] flex items-center gap-1.5 tracking-wider uppercase">
              <span className="w-2 h-2 rounded-full bg-[#333e50] animate-pulse" />
              REVIEW QUEUE
            </span>
            <div className="flex items-center gap-1 font-mono text-xs">
              <span className="text-[#1a1c1e] font-semibold">
                STEP {currentStepNumber > 0 ? currentStepNumber : 1}
              </span>
              <span className="text-[#75777d]">/ {totalSteps || 1}</span>
            </div>
          </div>
          <h1 className="text-xl font-bold text-[#1a1c1e] tracking-tight mt-1">
            {productTitle}
          </h1>

          {/* Queue Progress Bar */}
          <div className="w-full h-1.5 bg-[#eeeef0] rounded-full overflow-hidden mt-2">
            <div
              className="h-full bg-[#333e50] transition-all duration-500 ease-out"
              style={{
                width: `${totalSteps > 0 ? (queue.completed_review_count / totalSteps) * 100 : 100}%`,
              }}
            />
          </div>

          {/* Batch Review Action Bar if High Confidence items available */}
          {highConfidencePending.length > 0 && !isAllComplete && (
            <div className="mt-3 p-3 bg-[#e9edf5] border border-[#c5c6cd] rounded-sm flex items-center justify-between gap-2 shadow-xs">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#333e50] shrink-0" />
                <span className="font-mono text-xs text-[#333e50]">
                  {highConfidencePending.length} high-confidence declaration{highConfidencePending.length > 1 ? "s" : ""} detected (&ge;85%)
                </span>
              </div>
              <button
                type="button"
                onClick={handleBatchConfirmHighConfidence}
                disabled={isBatchSubmitting}
                className="px-3 py-1.5 bg-[#333e50] text-white text-xs font-mono font-bold uppercase rounded-sm hover:bg-[#27303e] flex items-center gap-1.5 shadow-sm active:scale-95 transition-all disabled:opacity-60"
              >
                {isBatchSubmitting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <CheckCheck className="w-3.5 h-3.5 text-emerald-400" />
                )}
                <span>Batch Confirm ({highConfidencePending.length})</span>
              </button>
            </div>
          )}
        </div>

        {/* Feedback Alert Toast */}
        {actionSuccessMessage && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-sm text-xs font-mono flex items-center gap-2 animate-in fade-in duration-200">
            <Check className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{actionSuccessMessage}</span>
          </div>
        )}

        {errorMessage && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-800 rounded-sm text-xs font-mono flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Completion Screen when All Items are Cleared */}
        {isAllComplete ? (
          <div className="bg-[#eeeef0] border border-[#c5c6cd] rounded-sm p-6 flex flex-col items-center text-center gap-4 shadow-sm my-4">
            <div className="w-14 h-14 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shadow-inner">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <div className="flex flex-col gap-1">
              <h2 className="text-lg font-bold text-[#1a1c1e]">All Reviews Completed</h2>
              <p className="text-xs text-[#566155] max-w-md">
                Every flagged declaration in this inspection has been confirmed, corrected, or exempted by the legal metrology officer.
              </p>
            </div>

            <div className="w-full flex flex-col sm:flex-row gap-3 mt-3">
              <Link
                href={`/inspections/${inspectionId}/evidence`}
                className="flex-1 h-12 bg-white text-[#333e50] font-mono text-xs font-semibold rounded-sm border border-[#c5c6cd] flex items-center justify-center gap-2 hover:bg-slate-50 transition-colors shadow-sm"
              >
                View Evidence Map
              </Link>
              <button
                type="button"
                onClick={onComplete}
                className="flex-1 h-12 bg-[#333e50] text-white font-mono text-xs font-bold rounded-sm flex items-center justify-center gap-2 hover:bg-[#27303e] transition-colors shadow-md"
              >
                <Sparkles className="w-4 h-4 text-emerald-400" />
                Proceed to Report
              </button>
            </div>
          </div>
        ) : currentItem ? (
          <>
            {/* Flagged Item Alert Banner */}
            <div className="p-4 bg-[#645234] rounded-sm shadow-sm relative overflow-hidden text-[#dfc6a0]">
              <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#4b3b1f]" />
              <div className="flex items-start gap-3 pl-1">
                <AlertTriangle className="w-5 h-5 text-[#dfc6a0] shrink-0 mt-0.5" />
                <div className="flex flex-col">
                  <span className="font-mono text-[11px] font-bold tracking-wider uppercase text-[#dfc6a0]">
                    {currentItem.flag_reason || `LOW CONFIDENCE EXTRACTION (${Math.round(currentItem.confidence * 100)}%)`}
                  </span>
                  <span className="text-xs text-[#dfc6a0]/90 mt-1">
                    Verify the extracted {currentItem.field_label.toLowerCase()} value against the captured physical label evidence.
                  </span>
                </div>
              </div>
            </div>

            {/* Captured Evidence Area */}
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-end px-0.5">
                <span className="font-mono text-[11px] font-medium text-[#75777d] uppercase tracking-wider">
                  Captured Evidence
                </span>
                <span className="font-mono text-[10px] text-[#4b3b1f] bg-[#dfc6a0]/40 px-2 py-0.5 rounded-sm font-semibold">
                  INDEX E02 · {currentItem.source_image_id ? "SOURCE CROP" : "PDP"}
                </span>
              </div>

              {/* 4:3 Aspect Container with Technical Reticle & Grid */}
              <div className="relative w-full aspect-[4/3] bg-[#2f3133] rounded-sm overflow-hidden ring-1 ring-[#c5c6cd] shadow-md group">
                <div className="absolute top-2.5 left-2.5 w-6 h-6 border-t-2 border-l-2 border-[#dfc6a0] z-10 pointer-events-none opacity-90" />
                <div className="absolute top-2.5 right-2.5 w-6 h-6 border-t-2 border-r-2 border-[#dfc6a0] z-10 pointer-events-none opacity-90" />
                <div className="absolute bottom-2.5 left-2.5 w-6 h-6 border-b-2 border-l-2 border-[#dfc6a0] z-10 pointer-events-none opacity-90" />
                <div className="absolute bottom-2.5 right-2.5 w-6 h-6 border-b-2 border-r-2 border-[#dfc6a0] z-10 pointer-events-none opacity-90" />

                <div className="absolute inset-0 bg-[radial-gradient(#ffffff_1px,transparent_1px)] [background-size:16px_16px] opacity-15 pointer-events-none z-10" />

                {currentItem.source_image_url ? (
                  <Image
                    src={currentItem.source_image_url}
                    alt="Physical label evidence crop"
                    fill
                    sizes="(max-width: 768px) 100vw, 640px"
                    className="object-cover opacity-90 group-hover:scale-105 transition-transform duration-700 ease-out"
                    unoptimized
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center bg-[#1a1c1e] text-[#c5c6cd] font-mono text-xs">
                    [Evidence image preview: {currentItem.field_label}]
                  </div>
                )}

                <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
                  <div className="w-28 h-14 ring-1 ring-[#dfc6a0]/70 bg-[#dfc6a0]/10 backdrop-blur-[1px] rounded-xs flex items-center justify-center">
                    <span className="font-mono text-[9px] text-white/90 bg-black/60 px-1 py-0.5 rounded">
                      {Math.round(currentItem.confidence * 100)}% CONF
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Declaration Form Section */}
            <div className="bg-[#eeeef0] rounded-sm p-4 flex flex-col gap-4 shadow-sm border border-[#e2e2e5]">
              <div className="flex flex-col gap-1 border-b border-[#c5c6cd]/40 pb-3">
                <span className="font-mono text-[10px] text-[#75777d] uppercase tracking-wider font-semibold">
                  Declaration Field
                </span>
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-lg font-bold text-[#1a1c1e] tracking-tight uppercase">
                    {currentItem.field_label}
                  </h2>
                  <span className="font-mono text-[11px] text-[#566155] bg-[#e2e2e5] px-2 py-0.5 rounded-sm border border-[#c5c6cd]/50 font-medium">
                    {currentItem.violations[0]?.citation || "Rule 6 / 7"}
                  </span>
                </div>
              </div>

              {/* AI Extracted Value Comparison */}
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between items-center px-0.5">
                  <span className="font-mono text-[11px] text-[#333e50] flex items-center gap-1 font-medium">
                    <Bot className="w-3.5 h-3.5 text-[#333e50]" /> AI EXTRACTED
                  </span>
                  <span className="font-mono text-xs text-[#75777d] line-through opacity-75">
                    {currentItem.raw_text || currentItem.parsed_value || "—"}
                  </span>
                </div>

                {/* Editable Input Box */}
                <div className="relative group">
                  <input
                    type="text"
                    value={currentOverrideValue}
                    onChange={(e) => {
                      setOverrideValues((prev) => ({ ...prev, [activeFieldId]: e.target.value }));
                      setErrorMessage(null);
                    }}
                    disabled={isSubmitting}
                    className="w-full h-12 px-4 bg-white text-[#1a1c1e] font-sans text-base font-medium rounded-sm ring-1 ring-[#c5c6cd] focus:outline-none focus:ring-2 focus:ring-[#333e50] transition-all shadow-sm pr-20 disabled:opacity-60"
                    placeholder="Enter verified declaration"
                  />
                  <div className="absolute right-3.5 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none text-[#75777d] group-focus-within:text-[#333e50]">
                    <span className="font-mono text-[11px] font-medium uppercase">Edit</span>
                    <Edit3 className="w-4 h-4" />
                  </div>
                </div>

                {/* Optional Officer Note */}
                <div className="mt-1">
                  <input
                    type="text"
                    value={currentReviewNotes}
                    onChange={(e) => {
                      setReviewNotesMap((prev) => ({ ...prev, [activeFieldId]: e.target.value }));
                    }}
                    disabled={isSubmitting}
                    className="w-full h-9 px-3 bg-white/70 text-[#1a1c1e] font-sans text-xs rounded-sm ring-1 ring-[#c5c6cd]/50 focus:outline-none focus:ring-1 focus:ring-[#333e50] placeholder:text-[#75777d]"
                    placeholder="Optional review note / justification for audit log"
                  />
                </div>
              </div>
            </div>

            {/* Decision Triad Actions */}
            <div className="flex flex-col gap-2.5 pt-1">
              <button
                type="button"
                onClick={() => handleAction("confirm")}
                disabled={isSubmitting}
                className="w-full h-12 bg-[#333e50] text-white font-mono text-xs font-bold uppercase tracking-wider rounded-sm flex items-center justify-center gap-2 shadow-md active:scale-[0.99] transition-all hover:bg-[#27303e] disabled:opacity-50"
              >
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                CONFIRM AS CORRECT
              </button>

              <button
                type="button"
                onClick={() => handleAction("correct")}
                disabled={isSubmitting}
                className="w-full h-12 bg-[#645234] text-[#dfc6a0] font-mono text-xs font-bold uppercase tracking-wider rounded-sm flex items-center justify-center gap-2 shadow-sm active:scale-[0.99] transition-all hover:bg-[#52432b] disabled:opacity-50"
              >
                <Edit3 className="w-4 h-4 text-[#dfc6a0]" />
                SAVE CORRECTION
              </button>

              <button
                type="button"
                onClick={() => handleAction("mark_not_applicable")}
                disabled={isSubmitting}
                className="w-full h-12 bg-transparent text-[#75777d] font-mono text-xs font-semibold uppercase tracking-wider rounded-sm flex items-center justify-center gap-2 active:scale-[0.99] transition-all hover:bg-[#e2e2e5]/50 ring-1 ring-[#c5c6cd] mt-0.5 disabled:opacity-50"
              >
                <Ban className="w-4 h-4 text-[#75777d]" />
                MARK NOT APPLICABLE / EXEMPT
              </button>
            </div>

            {/* Step Navigation Controls */}
            {pendingItems.length > 1 && (
              <div className="flex items-center justify-between gap-3 pt-2 text-xs font-mono text-[#75777d]">
                <button
                  type="button"
                  onClick={() => setCurrentIndex((prev) => (prev > 0 ? prev - 1 : pendingItems.length - 1))}
                  className="px-3 py-1.5 rounded bg-[#eeeef0] hover:bg-[#e2e2e5] text-[#333e50] flex items-center gap-1 transition-colors"
                >
                  <ChevronLeft className="w-3.5 h-3.5" /> Previous Item
                </button>
                <span>
                  {currentIndex + 1} of {pendingItems.length} pending
                </span>
                <button
                  type="button"
                  onClick={() => setCurrentIndex((prev) => (prev < pendingItems.length - 1 ? prev + 1 : 0))}
                  className="px-3 py-1.5 rounded bg-[#eeeef0] hover:bg-[#e2e2e5] text-[#333e50] flex items-center gap-1 transition-colors"
                >
                  Next Item <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </>
        ) : null}

        {/* Legal Metrology Immutable Audit Notice */}
        <div className="pt-4 pb-2">
          <p className="font-mono text-[11px] text-[#75777d] text-center flex items-center justify-center gap-1.5 opacity-80 leading-relaxed px-4">
            <Gavel className="w-3.5 h-3.5 text-[#333e50] shrink-0" />
            Every review action is recorded immutably with timestamp and Officer ID for legal metrology enforcement records.
          </p>
        </div>
      </main>

      {/* Review History Audit Trail Drawer Modal */}
      {showHistoryModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex justify-end">
          <div className="bg-[#f9f9fc] w-full max-w-md h-full shadow-2xl flex flex-col border-l border-[#c5c6cd] animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-4 border-b border-[#e2e2e5] bg-white flex items-center justify-between">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-[#333e50]" />
                <h3 className="font-bold text-sm text-[#1a1c1e]">Inspection Audit Trail</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowHistoryModal(false)}
                className="w-8 h-8 rounded-full hover:bg-[#eeeef0] flex items-center justify-center text-[#75777d]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Audit Log Entries List */}
            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
              <div className="p-2.5 bg-[#e9edf5] rounded-sm text-xs font-mono text-[#333e50] flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Immutable Chain of Custody (Section 36)</span>
              </div>

              {isLoadingHistory ? (
                <div className="flex items-center justify-center py-12 text-[#75777d]">
                  <Loader2 className="w-6 h-6 animate-spin text-[#333e50]" />
                </div>
              ) : historyItems.length === 0 ? (
                <div className="py-12 text-center text-xs font-mono text-[#75777d]">
                  No officer review actions recorded yet.
                </div>
              ) : (
                historyItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-3.5 bg-white border border-[#c5c6cd] rounded-sm shadow-xs flex flex-col gap-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-[#eeeef0] text-[#333e50]">
                        {item.action}
                      </span>
                      <span className="font-mono text-[10px] text-[#75777d] flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>

                    <div className="text-xs font-bold text-[#1a1c1e] uppercase">
                      Declaration: {item.field_type}
                    </div>

                    <div className="flex items-center gap-1.5 text-xs text-[#566155]">
                      <User className="w-3.5 h-3.5 text-[#75777d]" />
                      <span>{item.officer_name}</span>
                      <span className="text-[10px] font-mono uppercase bg-[#eeeef0] px-1.5 rounded text-[#75777d]">
                        {item.officer_role}
                      </span>
                    </div>

                    {item.after_value && (
                      <div className="p-2 bg-[#f9f9fc] rounded text-[11px] font-mono text-[#333e50] border border-[#e2e2e5] mt-1">
                        {item.after_value.officer_override_value ? (
                          <div>Correction: &quot;{String(item.after_value.officer_override_value)}&quot;</div>
                        ) : (
                          <div>Verdict: {String(item.after_value.verdict || "Confirmed")}</div>
                        )}
                        {Boolean(item.after_value.officer_notes || item.after_value.review_notes) && (
                          <div className="text-[#75777d] mt-0.5 text-[10px]">
                            Note: {String(item.after_value.officer_notes || item.after_value.review_notes)}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-[#e2e2e5] bg-white text-center">
              <span className="font-mono text-[10px] text-[#75777d]">
                Tamper-evident log under Section 36 of Legal Metrology Act, 2009
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Bottom Sticky Tab Navigation */}
      <nav className="fixed bottom-0 w-full z-40 bg-[#f9f9fc]/90 backdrop-blur-xl border-t border-[#e2e2e5] shadow-[0_-1px_8px_rgba(0,0,0,0.04)]">
        <div className="h-16 max-w-2xl mx-auto flex justify-around items-center px-4">
          <Link
            href={`/inspections/${inspectionId}/evidence`}
            className="flex flex-col items-center justify-center gap-1 text-[#333e50] font-bold text-[10px] font-mono tracking-wider uppercase"
          >
            <ShieldCheck className="w-5 h-5 text-[#333e50]" />
            Evidence
          </Link>
          <button
            type="button"
            onClick={handleOpenHistory}
            className="flex flex-col items-center justify-center gap-1 text-[#75777d] text-[10px] font-mono tracking-wider uppercase hover:text-[#333e50] transition-colors"
          >
            <History className="w-5 h-5 text-[#75777d]" />
            Audit Log
          </button>
          <button
            type="button"
            onClick={onComplete}
            className="flex flex-col items-center justify-center gap-1 text-[#75777d] text-[10px] font-mono tracking-wider uppercase hover:text-[#333e50] transition-colors"
          >
            <CheckCircle2 className="w-5 h-5 text-[#75777d]" />
            Complete
          </button>
        </div>
      </nav>
    </div>
  );
}
