"use client";

import React, { useEffect, useState } from "react";
import { useServerHealth } from "@/app/hooks/useServerHealth";
import { Server, AlertCircle, CheckCircle2, RefreshCw } from "lucide-react";

export default function ColdStartBanner() {
  const { status, elapsedSeconds, isColdStarting, recheck } = useServerHealth();
  const [visible, setVisible] = useState<boolean>(false);
  const [showConnectedToast, setShowConnectedToast] = useState<boolean>(false);

  useEffect(() => {
    if (isColdStarting) {
      setVisible(true);
    } else if (status === "online" && visible) {
      setShowConnectedToast(true);
      const timer = setTimeout(() => {
        setShowConnectedToast(false);
        setVisible(false);
      }, 3500);
      return () => clearTimeout(timer);
    }
  }, [status, isColdStarting, visible]);

  if (!visible && !showConnectedToast) {
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
                onClick={() => recheck()}
                className="text-[10px] uppercase font-bold text-[#E65100] hover:text-[#BF360C] flex items-center gap-1 cursor-pointer"
                title="Retry ping"
              >
                <RefreshCw className="w-3 h-3 animate-spin" />
                Ping
              </button>
            </div>
            <p className="text-[11px] text-[#795548] mt-0.5 leading-snug">
              Render free tier container boots in ~30s after inactivity. Offline camera & local inspection queuing remain 100% active.
            </p>
          </div>
        </div>
      ) : status === "error" ? (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-[#FBE9E7] text-[#BF360C] border border-[#FFCCBC] rounded-xl shadow-md text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-[#D84315]" />
          <span className="flex-1">Backend asleep or offline. Local inspections will sync automatically when reachable.</span>
          <button
            onClick={() => recheck()}
            className="px-2 py-1 bg-white/80 border border-[#FFCCBC] rounded font-medium text-[10px] hover:bg-white cursor-pointer"
          >
            Retry
          </button>
        </div>
      ) : null}
    </aside>
  );
}
