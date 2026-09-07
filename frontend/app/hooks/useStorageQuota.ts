"use client";

import { useCallback, useEffect, useState } from "react";
import { checkStorageHealth, StorageHealthStatus } from "../utils/storageQuota";

const INITIAL_HEALTH: StorageHealthStatus = {
  isLowSpace: false,
  isQueueFull: false,
  isWarning: false,
  severity: "normal",
  queueCount: 0,
  maxQueueCount: 50,
  availableMB: 500,
  usagePercent: 0,
  title: "Checking Storage",
  message: "Calculating local storage quota...",
};

export function useStorageQuota() {
  const [health, setHealth] = useState<StorageHealthStatus>(INITIAL_HEALTH);
  const [isChecking, setIsChecking] = useState<boolean>(true);

  const refresh = useCallback(async () => {
    setIsChecking(true);
    try {
      const result = await checkStorageHealth();
      setHealth(result);
    } catch {
      // Keep previous state on transient failure
    } finally {
      setIsChecking(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    checkStorageHealth().then((result) => {
      if (isMounted) {
        setHealth(result);
        setIsChecking(false);
      }
    });

    // Check periodically or on window focus
    const handleFocus = () => {
      checkStorageHealth().then((result) => {
        if (isMounted) {
          setHealth(result);
        }
      });
    };

    window.addEventListener("focus", handleFocus);
    const interval = setInterval(handleFocus, 30000); // every 30s

    return () => {
      isMounted = false;
      window.removeEventListener("focus", handleFocus);
      clearInterval(interval);
    };
  }, []);

  return {
    health,
    isChecking,
    refresh,
  };
}
