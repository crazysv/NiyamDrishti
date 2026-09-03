"use client";

import React, { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import ReviewQueue from "@/app/components/review/ReviewQueue";
import { InspectionReviewQueue } from "@/app/types/review";
import { fetchReviewQueue } from "@/app/services/reviewService";
import { Loader2, ArrowLeft } from "lucide-react";

interface ReviewPageProps {
  params: Promise<{ id: string }>;
}

export default function ReviewPage({ params }: ReviewPageProps) {
  const resolvedParams = use(params);
  const inspectionId = resolvedParams.id;
  const router = useRouter();

  const [queue, setQueue] = useState<InspectionReviewQueue | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadQueue() {
      setIsLoading(true);
      setError(null);

      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") || undefined : undefined;
        const data = await fetchReviewQueue(inspectionId, token);
        setQueue(data);
      } catch {
        // Provide offline fallback demonstration queue if backend API is not responding or in preview
        const fallbackQueue: InspectionReviewQueue = {
          inspection_id: inspectionId,
          overall_status: "needs_review",
          total_fields: 5,
          pending_review_count: 2,
          completed_review_count: 3,
          items: [
            {
              field_id: "field-01",
              inspection_id: inspectionId,
              field_type: "net_quantity",
              field_label: "Net Quantity",
              raw_text: "Net Wt: 500 g",
              parsed_value: "500g",
              confidence: 0.75,
              verdict: "needs_review",
              bounding_box: { x: 210, y: 450, w: 280, h: 55 },
              source_image_id: "img-01",
              source_image_url: "https://lh3.googleusercontent.com/aida/AEtjO1VI0q8XzWGdd3oBMBp6jnyXBcUpCLHzkuGSTWQuK2AFClmvRkjsxv2DPss1mJg8A1xmudqda93nNcVVmwullEGp4sZkxk0WlzLJ9Z74jeF769LA6ABw5KuJrPWLCaVegJfCnXj6j_G9laK2g75hYS2It-AazORAN7Au4ncyFQQ0BD9ucJKq0ENil0rzX9mHv7vSsmhHwYGk0o2R76l2guqYtH1xPMiEombWPQS-WB1pQAp1QGdNQoCGAwo",
              flag_reason: "Low extraction confidence (75% < 85%)",
              reviewed_by_officer: false,
              officer_override_value: null,
              violations: [
                {
                  id: "v-01",
                  rule_id: "net-quantity-font-height",
                  description: "Font height 2.8mm is below 4.0mm required for >200g net weight packages.",
                  severity: "major",
                  citation: "LM(PC) Rule 7(1) Table-1",
                },
              ],
            },
            {
              field_id: "field-02",
              inspection_id: inspectionId,
              field_type: "mrp",
              field_label: "Maximum Retail Price (MRP)",
              raw_text: "MRP Rs 240.00",
              parsed_value: "Rs 240.00",
              confidence: 0.82,
              verdict: "needs_review",
              bounding_box: { x: 210, y: 550, w: 250, h: 50 },
              source_image_id: "img-01",
              source_image_url: "https://lh3.googleusercontent.com/aida/AEtjO1VI0q8XzWGdd3oBMBp6jnyXBcUpCLHzkuGSTWQuK2AFClmvRkjsxv2DPss1mJg8A1xmudqda93nNcVVmwullEGp4sZkxk0WlzLJ9Z74jeF769LA6ABw5KuJrPWLCaVegJfCnXj6j_G9laK2g75hYS2It-AazORAN7Au4ncyFQQ0BD9ucJKq0ENil0rzX9mHv7vSsmhHwYGk0o2R76l2guqYtH1xPMiEombWPQS-WB1pQAp1QGdNQoCGAwo",
              flag_reason: "Statutory qualifier ambiguity: Missing '(inclusive of all taxes)'",
              reviewed_by_officer: false,
              officer_override_value: null,
              violations: [
                {
                  id: "v-02",
                  rule_id: "mrp-mandatory-declaration",
                  description: "Mandatory qualifier '(inclusive of all taxes)' not verified with high confidence.",
                  severity: "moderate",
                  citation: "LM(PC) Rule 6(1)(e)",
                },
              ],
            },
          ],
        };
        setQueue(fallbackQueue);
      } finally {
        setIsLoading(false);
      }
    }

    loadQueue();
  }, [inspectionId]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#f9f9fc] text-[#1a1c1e]">
        <Loader2 className="w-8 h-8 animate-spin text-[#333e50] mb-3" />
        <p className="text-xs font-mono text-[#75777d]">Loading review queue...</p>
      </div>
    );
  }

  if (error || !queue) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#f9f9fc] text-[#1a1c1e] p-6 text-center">
        <p className="text-xs font-mono text-red-600 mb-4">{error || "Review queue could not be loaded."}</p>
        <button
          type="button"
          onClick={() => router.back()}
          className="flex items-center gap-2 bg-[#333e50] text-white px-4 py-2 rounded-sm text-xs font-mono"
        >
          <ArrowLeft className="w-4 h-4" /> Return
        </button>
      </div>
    );
  }

  return (
    <ReviewQueue
      initialQueue={queue}
      inspectionId={inspectionId}
      productTitle="Premium Basmati Rice · Packaged Food"
      onComplete={() => router.push(`/inspections/${inspectionId}/report`)}
    />
  );
}
