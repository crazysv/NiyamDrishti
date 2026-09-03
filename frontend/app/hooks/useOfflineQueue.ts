"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import {
  getPendingSyncCount,
  getDeadLetterCount,
  getFailedSyncCount,
  queueInspectionForSync,
  getStorageQuota,
  resolveInspectionConflict,
  discardOfflineInspection,
  OfflineInspection,
} from "@/app/db/dexie";
import { ImageRole, CommodityCategory } from "@/app/types/capture";
import { QualityAssessment } from "@/app/utils/qualityGate";
import { syncAllQueuedInspections, retryAllFailedInspections } from "@/app/services/syncService";
import {
  checkStorageHealth,
  StorageHealthStatus,
  MAX_OFFLINE_QUEUE_DEPTH,
} from "@/app/utils/storageQuota";

export function useOfflineQueue() {
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [deadLetterCount, setDeadLetterCount] = useState<number>(0);
  const [failedCount, setFailedCount] = useState<number>(0);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncProgress, setSyncProgress] = useState<{ current: number; total: number }>({
    current: 0,
    total: 0,
  });
  const [storageInfo, setStorageInfo] = useState<{
    usageMb: number;
    quotaMb: number;
    percentUsed: number;
    isLowSpace: boolean;
  }>({ usageMb: 0, quotaMb: 0, percentUsed: 0, isLowSpace: false });
  const [storageHealth, setStorageHealth] = useState<StorageHealthStatus>({
    isLowSpace: false,
    isQueueFull: false,
    isWarning: false,
    severity: "normal",
    queueCount: 0,
    maxQueueCount: MAX_OFFLINE_QUEUE_DEPTH,
    availableMB: 500,
    usagePercent: 0,
    title: "Storage Healthy",
    message: "Adequate storage available.",
  });

  const isSyncingRef = useRef(false);

  // Refresh pending count, dead letters, failed count & storage estimate
  const refreshQueueState = useCallback(async () => {
    try {
      const [pending, deadLetters, failed, quota, health] = await Promise.all([
        getPendingSyncCount(),
        getDeadLetterCount(),
        getFailedSyncCount(),
        getStorageQuota(),
        checkStorageHealth(),
      ]);

      setPendingCount(pending);
      setDeadLetterCount(deadLetters);
      setFailedCount(failed);
      setStorageInfo(quota);
      setStorageHealth(health);
    } catch {
      // Ignore initial render errors if IndexedDB is not yet open
    }
  }, []);

  // Sync now action
  const syncNow = useCallback(async () => {
    if (isSyncingRef.current) return;
    if (typeof navigator !== "undefined" && !navigator.onLine) return;

    isSyncingRef.current = true;
    setIsSyncing(true);
    try {
      await syncAllQueuedInspections(undefined, (current, total) => {
        setSyncProgress({ current, total });
      });
    } finally {
      await refreshQueueState();
      setIsSyncing(false);
      isSyncingRef.current = false;
      setSyncProgress({ current: 0, total: 0 });
    }
  }, [refreshQueueState]);

  // Retry all failed and dead-letter inspections
  const retryFailed = useCallback(async () => {
    if (isSyncingRef.current) return;
    if (typeof navigator !== "undefined" && !navigator.onLine) return;

    isSyncingRef.current = true;
    setIsSyncing(true);
    try {
      await retryAllFailedInspections();
    } finally {
      await refreshQueueState();
      setIsSyncing(false);
      isSyncingRef.current = false;
    }
  }, [refreshQueueState]);

  // Resolve conflict on inspection
  const resolveConflict = useCallback(
    async (inspectionId: string, strategy: "server_authoritative" | "discard") => {
      await resolveInspectionConflict(inspectionId, strategy);
      await refreshQueueState();
    },
    [refreshQueueState]
  );

  // Discard inspection from offline queue
  const discardInspection = useCallback(
    async (inspectionId: string) => {
      await discardOfflineInspection(inspectionId);
      await refreshQueueState();
    },
    [refreshQueueState]
  );

  // Load initial queue state asynchronously
  useEffect(() => {
    let isMounted = true;
    Promise.all([
      getPendingSyncCount(),
      getDeadLetterCount(),
      getFailedSyncCount(),
      getStorageQuota(),
      checkStorageHealth(),
    ]).then(([pending, deadLetters, failed, quota, health]) => {
      if (isMounted) {
        setPendingCount(pending);
        setDeadLetterCount(deadLetters);
        setFailedCount(failed);
        setStorageInfo(quota);
        setStorageHealth(health);
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  // Listen for online event to automatically resume syncing
  useEffect(() => {
    const handleOnline = () => {
      syncNow();
    };

    window.addEventListener("online", handleOnline);
    return () => {
      window.removeEventListener("online", handleOnline);
    };
  }, [syncNow]);

  // Queue an inspection
  const queueInspection = async (
    inspectionId: string,
    category: CommodityCategory,
    images: { role: ImageRole; dataUrl: string; qualityAssessment?: QualityAssessment }[],
    isOffline: boolean
  ): Promise<OfflineInspection> => {
    const health = await checkStorageHealth();
    if (health.isQueueFull) {
      throw new Error(
        `Offline queue limit reached (${MAX_OFFLINE_QUEUE_DEPTH} packages). Please connect to internet to sync pending packages.`
      );
    }

    const saved = await queueInspectionForSync(inspectionId, category, images, isOffline);
    await refreshQueueState();

    // If device is online, trigger sync immediately in the background
    if (typeof navigator !== "undefined" && navigator.onLine) {
      syncNow();
    }

    return saved;
  };

  return {
    pendingCount,
    deadLetterCount,
    failedCount,
    isSyncing,
    syncProgress,
    storageInfo,
    storageHealth,
    refreshQueueState,
    syncNow,
    retryFailed,
    resolveConflict,
    discardInspection,
    queueInspection,
  };
}
