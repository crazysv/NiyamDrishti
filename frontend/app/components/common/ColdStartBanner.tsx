"use client";

import React, { useEffect, useState, useRef } from "react";
import { useServerHealth } from "@/app/hooks/useServerHealth";
import { Server, CheckCircle2, RefreshCw } from "lucide-react";

export default function ColdStartBanner() {
  const { status, elapsedSeconds, isColdStarting, recheck } = useServerHealth();
  const [showConnectedToast, setShowConnectedToast] = useState<boolean>(false);
  const wasColdStartingRef = useRef<boolean>(false);

  useEffect(() => {
    if (isColdStarting) {
      wasColdStartingRef.current = true;
    } else if (status === "online" && wasColdStartingRef.current) {
      wasColdStartingRef.current = false;
      const showTimer = setTimeout(() => {
        setShowConnectedToast(true);
      }, 0);
      const hideTimer = setTimeout(() => {
        setShowConnectedToast(false);
      }, 3500);
      return () => {
        clearTimeout(showTimer);
        clearTimeout(hideTimer);
      };
    }
  }, [status, isColdStarting]);

  if (!isColdStarting && !showConnectedToast) {
    return null;
  }

  return (
    <aside
      aria-label="Server status alert"
      className="fixed top-3 left-1/2 -translate-x-1/2 z-50 w-[92%] max-w-lg transition-all duration-300 ease-out"
    >
      {showConnectedToast ? (
        <div className="flex items-center gap-3 px-4 py-3 bg-[#E8F5E9] text-[#1B5E20] border border-[#A5D6A7] rounded-xl shadow-lg shadow-black/5 animate-in fade-in slide-in-from-top-2">
          <CheckCircle2 className="w-5 h-5 text-[#2E7D32] shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold">Backend Connected</p>
            <p className="text-[11px] text-[#2E7D32]">Server online and ready for high-precision OCR processing.</p>
          </div>
        </div>
      ) : isColdStarting ? (
        <div className="flex items-start gap-3 px-4 py-3 bg-[#FFF8E1] text-[#E65100] border border-[#FFE082] rounded-xl shadow-lg shadow-black/10 animate-in fade-in slide-in-from-top-2">
          <div className="relative mt-0.5 shrink-0">
            <Server className="w-5 h-5 text-[#F57C00]" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-amber-500 rounded-full animate-ping" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-[#BF360C]">
                Waking Server from Sleep ({elapsedSeconds}s)
              </p>
              <button
                onClick={() => void recheck()}
                className="text-[10px] uppercase font-bold text-[#E65100] hover:text-[#BF360C] flex items-center gap-1 cursor-pointer"
                title="Retry ping"
              >
                <RefreshCw className="w-3 h-3 animate-spin" />
                Ping
              </button>
            </div>
            <p className="text-[11px] text-[#E65100] mt-0.5 leading-relaxed">
              Render container spinning up from idle (~30s). You can continue capturing packaging photos offline — they will automatically sync once connected.
            </p>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
