"use client";

import React from "react";
import { StorageHealthStatus } from "../../utils/storageQuota";

interface StorageWarningBannerProps {
  health: StorageHealthStatus;
  onSyncClick?: () => void;
}

export const StorageWarningBanner: React.FC<StorageWarningBannerProps> = ({
  health,
  onSyncClick,
}) => {
  if (!health.isWarning) {
    return null;
  }

  const isCritical = health.severity === "critical";

  const containerBg = isCritical ? "bg-[#ffdad6]" : "bg-[#dfc6a0]";
  const borderColor = isCritical ? "border-[#ba1a1a]" : "border-[#645234]";
  const titleColor = isCritical ? "text-[#93000a]" : "text-[#4b3b1f]";
  const textColor = isCritical ? "text-[#410002]" : "text-[#2e2311]";
  const buttonBg = isCritical ? "bg-[#ba1a1a] text-white" : "bg-[#645234] text-white";

  return (
    <aside
      aria-label="Storage Status Warning"
      className={`w-full border-l-4 p-3.5 mb-4 rounded-r-md ${containerBg} ${borderColor} shadow-sm transition-all duration-200`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <span className="text-lg leading-none select-none mt-0.5" aria-hidden="true">
            {isCritical ? "⚠️" : "💾"}
          </span>
          <div>
            <h4 className={`text-xs font-bold uppercase tracking-wider ${titleColor}`}>
              {health.title}
            </h4>
            <p className={`text-xs mt-0.5 leading-relaxed ${textColor}`}>
              {health.message}
            </p>
            <div className="flex items-center gap-3 mt-1.5 text-[11px] opacity-80 font-mono">
              <span>Queue: {health.queueCount}/{health.maxQueueCount}</span>
              <span>Available: ~{health.availableMB}MB</span>
              {health.usagePercent > 0 && <span>Used: {health.usagePercent}%</span>}
            </div>
          </div>
        </div>

        {onSyncClick && (
          <button
            type="button"
            onClick={onSyncClick}
            className={`px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded shrink-0 ${buttonBg} hover:opacity-90 active:scale-95 transition`}
          >
            Sync Now
          </button>
        )}
      </div>
    </aside>
  );
};
