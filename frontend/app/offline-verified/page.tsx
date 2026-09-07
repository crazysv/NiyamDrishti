"use client";

import { useEffect, useState } from "react";
import OfflineVerifiedCheck from "@/app/components/offline/OfflineVerifiedCheck";

export default function OfflineVerifiedPage() {
  const [inspectionId, setInspectionId] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setInspectionId(sessionStorage.getItem("offline_verified_inspection_id"));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  if (inspectionId === null) {
    return <main className="min-h-screen bg-[#f9f9fc]" aria-label="Preparing offline check" />;
  }

  if (!inspectionId) {
    return <main className="min-h-screen bg-[#f9f9fc] p-6 text-sm text-[#44474c]">Capture a package before opening Offline Verified Check.</main>;
  }

  return <OfflineVerifiedCheck inspectionId={inspectionId} />;
}
