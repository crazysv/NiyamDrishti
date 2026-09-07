"use client";

import { useEffect, useState, useRef, useCallback } from "react";

export type ServerHealthState = "idle" | "checking" | "waking" | "online" | "error";

export interface ServerHealthInfo {
  status: ServerHealthState;
  elapsedSeconds: number;
  isColdStarting: boolean;
  recheck: () => Promise<void>;
}

export function useServerHealth(): ServerHealthInfo {
  const [status, setStatus] = useState<ServerHealthState>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const wakeTimerRef = useRef<NodeJS.Timeout | null>(null);

  const checkHealth = useCallback(async () => {
    setStatus("checking");

    // If server takes longer than 1.8s to respond, it is likely sleeping (Render free tier cold start)
    if (wakeTimerRef.current) clearTimeout(wakeTimerRef.current);
    wakeTimerRef.current = setTimeout(() => {
      setStatus("waking");
    }, 1800);

    // Increment elapsed timer while waking
    if (timerRef.current) clearInterval(timerRef.current);
    setElapsedSeconds(0);
    timerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";
      const res = await fetch(`${apiBase}/health`, {
        method: "GET",
        headers: { "Cache-Control": "no-cache" },
        signal: AbortSignal.timeout(60000), // 60s timeout to allow Render free-tier container boot
      });

      if (wakeTimerRef.current) clearTimeout(wakeTimerRef.current);
      if (timerRef.current) clearInterval(timerRef.current);

      if (res.ok) {
        setStatus("online");
      } else {
        setStatus("error");
      }
    } catch {
      if (wakeTimerRef.current) clearTimeout(wakeTimerRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    // Run asynchronously on mount if client is online
    const timer = setTimeout(() => {
      if (typeof window !== "undefined" && navigator.onLine) {
        void checkHealth();
      }
    }, 0);

    return () => {
      clearTimeout(timer);
      if (timerRef.current) clearInterval(timerRef.current);
      if (wakeTimerRef.current) clearTimeout(wakeTimerRef.current);
    };
  }, [checkHealth]);

  return {
    status,
    elapsedSeconds,
    isColdStarting: status === "waking",
    recheck: checkHealth,
  };
}
