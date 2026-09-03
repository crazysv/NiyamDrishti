"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";
import Link from "next/link";
import Webcam from "react-webcam";
import {
  Camera,
  Check,
  CheckCircle2,
  Flashlight,
  FlashlightOff,
  History,
  Image as ImageIcon,
  RotateCcw,
  Settings,
  Trash2,
  User,
  Wifi,
  WifiOff,
  SwitchCamera,
  Upload,
  AlertTriangle,
  AlertCircle,
  CheckCheck,
  CloudUpload,
  HardDrive,
  ShieldCheck,
  X,
  ExternalLink,
} from "lucide-react";
import {
  CAPTURE_SLOTS,
  CapturedImage,
  CommodityCategory,
  ImageRole,
} from "@/app/types/capture";
import {
  assessImageQuality,
  QualityAssessment,
} from "@/app/utils/qualityGate";
import { useOfflineQueue } from "@/app/hooks/useOfflineQueue";
import { StorageWarningBanner } from "../storage/StorageWarningBanner";
import {
  authorizeSandboxPersona,
  handleSSOCallback,
} from "@/app/services/ssoService";

// Subscribe to online/offline status using React's useSyncExternalStore
function useOnlineStatus() {
  return React.useSyncExternalStore(
    (callback) => {
      window.addEventListener("online", callback);
      window.addEventListener("offline", callback);
      return () => {
        window.removeEventListener("online", callback);
        window.removeEventListener("offline", callback);
      };
    },
    () => navigator.onLine,
    () => true // SSR default
  );
}

export default function CaptureScreen() {
  // Multi-image state
  const [images, setImages] = useState<Record<ImageRole, CapturedImage | null>>({
    front_pdp: null,
    back_panel: null,
    side_panel: null,
    sticker: null,
    ecommerce_listing: null,
  });

  const [activeSlot, setActiveSlot] = useState<ImageRole>("front_pdp");
  const [category, setCategory] = useState<CommodityCategory>("general");
  const isOnline = useOnlineStatus();
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const [torchOn, setTorchOn] = useState<boolean>(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isCapturing, setIsCapturing] = useState<boolean>(false);
  const [isAssessing, setIsAssessing] = useState<boolean>(false);
  const [isQueueing, setIsQueueing] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isProfileOpen, setIsProfileOpen] = useState<boolean>(false);
  const [currentUser, setCurrentUser] = useState<{
    id?: string;
    full_name?: string;
    email?: string;
    role?: string;
    region?: string | null;
  } | null>(null);
  const [isSwitchingPersona, setIsSwitchingPersona] = useState<boolean>(false);

  // Auto-login default sandbox officer on mount if unauthenticated
  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedUser = localStorage.getItem("user");
    const storedToken = localStorage.getItem("access_token");
    if (storedUser && storedToken) {
      try {
        setCurrentUser(JSON.parse(storedUser));
        return;
      } catch {
        // Fall through to auto-login
      }
    }
    const autoLogin = async () => {
      try {
        const authRes = await authorizeSandboxPersona("officer_suresh", "auto_init_" + Date.now());
        const tokenRes = await handleSSOCallback(authRes.code, authRes.state);
        setCurrentUser(tokenRes.user);
      } catch (err) {
        console.warn("[SSO] Auto-provisioning sandbox persona:", err);
      }
    };
    autoLogin();
  }, []);

  const handleSwitchPersona = async (personaId: string) => {
    setIsSwitchingPersona(true);
    try {
      const authRes = await authorizeSandboxPersona(personaId, "switch_state_" + Date.now());
      const tokenRes = await handleSSOCallback(authRes.code, authRes.state);
      setCurrentUser(tokenRes.user);
      setToastMessage(`Switched persona to ${tokenRes.user.full_name} (${tokenRes.user.role.toUpperCase()})`);
      setIsProfileOpen(false);
      setTimeout(() => setToastMessage(null), 3000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to switch persona";
      setToastMessage(msg);
      setTimeout(() => setToastMessage(null), 3500);
    } finally {
      setIsSwitchingPersona(false);
    }
  };

  const {
    pendingCount,
    isSyncing,
    syncProgress,
    storageInfo,
    storageHealth,
    queueInspection,
    syncNow,
  } = useOfflineQueue();

  const webcamRef = useRef<Webcam>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Video constraints
  const videoConstraints = {
    facingMode: facingMode,
    width: { ideal: 1920 },
    height: { ideal: 1080 },
  };

  // Process and assess a captured or uploaded image
  const processImage = useCallback(
    async (
      dataUrl: string,
      role: ImageRole,
      fileName?: string,
      fileSize?: number
    ) => {
      setIsAssessing(true);
      const assessment: QualityAssessment = await assessImageQuality(dataUrl);

      const newImage: CapturedImage = {
        id: `img_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
        role,
        dataUrl,
        capturedAt: new Date().toISOString(),
        fileName,
        fileSize,
        qualityAssessment: assessment,
      };

      setImages((prev) => ({
        ...prev,
        [role]: newImage,
      }));

      setIsAssessing(false);

      // If passed quality check, advance to next unfilled required slot
      if (assessment.passed) {
        if (role === "front_pdp" && !images.back_panel) {
          setActiveSlot("back_panel");
        } else if (role === "back_panel" && !images.sticker) {
          setActiveSlot("sticker");
        }
      }
    },
    [images]
  );

  // Capture frame from webcam
  const handleCapture = useCallback(async () => {
    if (!webcamRef.current) return;
    setIsCapturing(true);

    const imageSrc = webcamRef.current.getScreenshot();
    if (imageSrc) {
      await processImage(imageSrc, activeSlot);
    }

    setTimeout(() => setIsCapturing(false), 300);
  }, [activeSlot, processImage]);

  // Handle file picker selection
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
      const dataUrl = event.target?.result as string;
      if (dataUrl) {
        await processImage(dataUrl, activeSlot, file.name, file.size);
      }
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  // Remove photo from slot
  const handleRemoveSlotImage = (role: ImageRole) => {
    setImages((prev) => ({
      ...prev,
      [role]: null,
    }));
  };

  // Override quality failure (officer final authority per G6)
  const handleOfficerOverride = (role: ImageRole) => {
    setImages((prev) => {
      const current = prev[role];
      if (!current || !current.qualityAssessment) return prev;
      return {
        ...prev,
        [role]: {
          ...current,
          isAuthoritative: true,
          qualityAssessment: {
            ...current.qualityAssessment,
            passed: true,
            statusText: "OFFICER OVERRIDE ACCEPTED",
          },
        },
      };
    });

    if (role === "front_pdp" && !images.back_panel) {
      setActiveSlot("back_panel");
    }
  };

  // Queue current inspection package into IndexedDB
  const handleSaveAndQueue = async () => {
    const validImages: {
      role: ImageRole;
      dataUrl: string;
      qualityAssessment?: QualityAssessment;
    }[] = [];

    if (images.front_pdp) {
      validImages.push({
        role: "front_pdp",
        dataUrl: images.front_pdp.dataUrl,
        qualityAssessment: images.front_pdp.qualityAssessment,
      });
    }
    if (images.back_panel) {
      validImages.push({
        role: "back_panel",
        dataUrl: images.back_panel.dataUrl,
        qualityAssessment: images.back_panel.qualityAssessment,
      });
    }
    if (images.sticker) {
      validImages.push({
        role: "sticker",
        dataUrl: images.sticker.dataUrl,
        qualityAssessment: images.sticker.qualityAssessment,
      });
    }
    if (images.ecommerce_listing) {
      validImages.push({
        role: "ecommerce_listing",
        dataUrl: images.ecommerce_listing.dataUrl,
        qualityAssessment: images.ecommerce_listing.qualityAssessment,
      });
    }

    if (validImages.length === 0) return;

    if (storageHealth?.isQueueFull) {
      setToastMessage(
        `Offline storage limit reached (${storageHealth.maxQueueCount} packages). Please connect to internet to sync.`
      );
      setTimeout(() => setToastMessage(null), 4000);
      return;
    }

    setIsQueueing(true);
    const inspectionId = `insp_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;

    try {
      await queueInspection(inspectionId, category, validImages, !isOnline);

      // Show toast
      setToastMessage(
        isOnline
          ? "Inspection queued! Ready to sync to server."
          : "Saved locally! Will sync automatically when back online."
      );
      setTimeout(() => setToastMessage(null), 3500);

      // Reset slots for the next package so officer can keep going without being blocked
      setImages({
        front_pdp: null,
        back_panel: null,
        side_panel: null,
        sticker: null,
        ecommerce_listing: null,
      });
      setActiveSlot("front_pdp");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save to offline storage";
      setToastMessage(msg);
      setTimeout(() => setToastMessage(null), 3500);
    } finally {
      setIsQueueing(false);
    }
  };

  // Toggle torch / flash
  const toggleTorch = async () => {
    try {
      const stream = webcamRef.current?.video?.srcObject as MediaStream | undefined;
      const track = stream?.getVideoTracks()[0];
      if (track && "applyConstraints" in track) {
        const nextTorch = !torchOn;
        // @ts-expect-error Torch is non-standard in web types
        await track.applyConstraints({ advanced: [{ torch: nextTorch }] });
        setTorchOn(nextTorch);
      } else {
        setTorchOn(!torchOn);
      }
    } catch {
      setTorchOn(!torchOn);
    }
  };

  const activeImage = images[activeSlot];
  const filledCount = Object.values(images).filter(Boolean).length;
  const requiredCount = CAPTURE_SLOTS.filter((s) => s.isRequired).length;
  const isRequiredComplete = !!(images.front_pdp && images.back_panel);

  return (
    <div className="flex flex-col w-full max-w-md mx-auto min-h-screen bg-[#F9F7F2] text-[#1A1C1E] shadow-2xl relative select-none">
      {/* Hidden File Input for Gallery / Upload Fallback */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={handleFileUpload}
      />

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-14 inset-x-4 max-w-sm mx-auto z-50 bg-[#333E50] text-white px-4 py-2.5 rounded-lg shadow-xl text-xs font-mono-data flex items-center justify-between border border-white/20 animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{toastMessage}</span>
          </div>
          <button
            onClick={() => setToastMessage(null)}
            className="text-white/60 hover:text-white ml-2 text-sm"
          >
            ✕
          </button>
        </div>
      )}

      {/* Low Storage Warning (CAP-07 / STOR-03) */}
      {storageInfo.isLowSpace && (
        <div className="bg-amber-100 text-amber-900 border-b border-amber-300 px-3 py-1.5 text-[11px] font-mono-data flex items-center gap-1.5">
          <HardDrive className="w-3.5 h-3.5 text-amber-700 shrink-0" />
          <span>
            Low device storage ({storageInfo.usageMb}MB / {storageInfo.quotaMb}MB). Please sync or free space.
          </span>
        </div>
      )}

      {/* Resumable Sync Banner on Reconnect (CAP-09) */}
      {isSyncing ? (
        <div className="bg-[#EAE7DC] text-[#333E50] border-b border-[#D1CDC2] px-3 py-1.5 text-[11px] font-mono-data flex items-center justify-between animate-pulse">
          <div className="flex items-center gap-2">
            <CloudUpload className="w-3.5 h-3.5 text-[#333E50] shrink-0" />
            <span>
              Syncing queued items... ({syncProgress.current}/{syncProgress.total || pendingCount})
            </span>
          </div>
        </div>
      ) : pendingCount > 0 ? (
        <div className="bg-[#EAE7DC] text-[#333E50] border-b border-[#D1CDC2] px-3 py-1.5 text-[11px] font-mono-data flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <CloudUpload className="w-3.5 h-3.5 text-[#566155] shrink-0" />
            <span>
              {pendingCount} inspection{pendingCount > 1 ? "s" : ""} pending sync
            </span>
          </div>
          {isOnline && (
            <button
              onClick={() => syncNow()}
              className="px-2 py-0.5 bg-[#4A5568] hover:bg-[#333E50] text-white rounded text-[10px] font-mono-data font-bold transition-all active:scale-95"
            >
              SYNC NOW
            </button>
          )}
        </div>
      ) : null}

      {/* Header */}
      <header className="sticky top-0 z-40 bg-[#F9F7F2]/90 backdrop-blur-md border-b border-[#D1CDC2] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded bg-[#4A5568] flex items-center justify-center text-white font-mono-data font-bold text-xs shadow-sm">
            ND
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-base tracking-tight leading-none text-[#1A1C1E]">
              NiyamDrishti
            </span>
            <span className="font-mono-data text-[10px] text-[#75777D] tracking-wider uppercase mt-0.5">
              Evidence System
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Online/Offline Status Pill */}
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-mono-data font-medium transition-all ${
              isOnline
                ? "bg-[#D6E3D3]/60 border-[#BDCABA] text-[#3E4A3E]"
                : "bg-[#FFDAD6]/60 border-[#FFB4AB] text-[#BA1A1A]"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isOnline ? "bg-emerald-600 animate-pulse" : "bg-red-500"
              }`}
            />
            {isOnline ? "ONLINE" : "OFFLINE"}
          </div>

          <button
            onClick={() => setIsProfileOpen(true)}
            aria-label="Officer Profile"
            className="w-8 h-8 rounded-full bg-[#333E50] flex items-center justify-center text-white shadow-sm hover:opacity-90 active:scale-95 relative"
          >
            <User className="w-4 h-4 text-white" />
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-500 rounded-full border border-white" />
          </button>
        </div>
      </header>

      {/* Storage Capacity Warning Banner (STOR-03) */}
      {storageHealth?.isWarning && (
        <div className="px-4 pt-2.5 bg-[#F9F7F2]">
          <StorageWarningBanner health={storageHealth} onSyncClick={syncNow} />
        </div>
      )}

      {/* Top Metadata Bar */}
      <div className="px-4 py-2 flex justify-between items-center bg-[#F9F7F2] border-b border-[#D1CDC2] text-xs">
        <div className="flex items-center gap-2 text-[#75777D] font-mono-data text-[11px]">
          {isOnline ? (
            <Wifi className="w-3.5 h-3.5 text-[#566155]" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-[#BA1A1A]" />
          )}
          <span>
            {pendingCount > 0
              ? `${pendingCount} PENDING SYNC`
              : isOnline
              ? "READY FOR SCAN"
              : "OFFLINE · SAVED LOCALLY"}
          </span>
        </div>

        {/* Category Selector */}
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value as CommodityCategory)}
          className="appearance-none bg-[#F0EDE5] border border-[#D1CDC2] rounded px-2.5 py-1 font-mono-data text-[11px] font-medium text-[#4A5568] focus:outline-none focus:border-[#333E50] cursor-pointer"
        >
          <option value="general">CAT: GENERAL</option>
          <option value="packaged_food">CAT: PACKAGED FOOD</option>
          <option value="electronics">CAT: ELECTRONICS</option>
          <option value="pan_masala">CAT: PAN MASALA</option>
          <option value="medical_device">CAT: MEDICAL DEVICE</option>
        </select>
      </div>

      {/* Live Viewfinder Section (Aspect 3:4) */}
      <div className="relative w-full aspect-[3/4] bg-[#2F3133] overflow-hidden flex items-center justify-center">
        {/* Assessing Loader Overlay */}
        {isAssessing && (
          <div className="absolute inset-0 bg-black/60 backdrop-blur-xs z-30 flex flex-col items-center justify-center text-white">
            <div className="w-8 h-8 border-2 border-white/30 border-t-white rounded-full animate-spin mb-2" />
            <span className="font-mono-data text-xs tracking-wider">
              RUNNING QUALITY GATE...
            </span>
          </div>
        )}

        {/* If Active Slot has a photo, show preview + Quality Assessment */}
        {activeImage ? (
          <div className="relative w-full h-full">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={activeImage.dataUrl}
              alt={`Captured ${activeSlot}`}
              className="w-full h-full object-cover"
            />

            {/* Quality Status Banner (Top) */}
            <div
              className={`absolute top-0 inset-x-0 px-4 py-2 border-b flex items-center justify-between shadow-sm z-10 backdrop-blur-md ${
                activeImage.qualityAssessment?.passed
                  ? "bg-[#D6E3D3]/95 border-[#BDCABA] text-[#3E4A3E]"
                  : "bg-[#FFDAD6]/95 border-[#FFB4AB] text-[#BA1A1A]"
              }`}
            >
              <div className="flex items-center gap-2">
                {activeImage.qualityAssessment?.passed ? (
                  <CheckCircle2 className="w-4 h-4 text-[#3E4A3E]" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-[#BA1A1A]" />
                )}
                <span className="font-mono-data text-[11px] font-bold tracking-wide uppercase">
                  {activeImage.qualityAssessment?.statusText || "IMAGE CAPTURED"}
                </span>
              </div>
              <span className="font-mono-data text-[10px] font-semibold">
                SCORE: {activeImage.qualityAssessment?.score ?? 100}/100
              </span>
            </div>

            {/* Quality Failure Specific Retake Guidance Drawer (Bottom Overlay) */}
            {!activeImage.qualityAssessment?.passed && activeImage.qualityAssessment?.issues.length ? (
              <div className="absolute bottom-16 inset-x-3 bg-white/95 backdrop-blur-md rounded border border-red-300 p-3 shadow-xl z-20 animate-in fade-in slide-in-from-bottom-2">
                <div className="flex items-start gap-2 mb-2">
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-xs font-bold text-red-950">
                      {activeImage.qualityAssessment.issues[0].title}
                    </p>
                    <p className="text-[11px] text-gray-700 mt-0.5">
                      {activeImage.qualityAssessment.issues[0].message}
                    </p>
                    <p className="text-[11px] font-semibold text-red-800 mt-1 bg-red-50 p-1.5 rounded border border-red-200">
                      👉 Retake Action: {activeImage.qualityAssessment.issues[0].actionHint}
                    </p>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 mt-2 pt-2 border-t border-gray-200">
                  <button
                    onClick={() => handleOfficerOverride(activeSlot)}
                    className="px-2.5 py-1 text-[11px] font-mono-data text-gray-600 hover:text-gray-900"
                  >
                    Accept Anyway (Officer Call)
                  </button>
                  <button
                    onClick={() => handleRemoveSlotImage(activeSlot)}
                    className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-xs font-mono-data flex items-center gap-1.5 shadow-sm active:scale-95"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>Retake Photo</span>
                  </button>
                </div>
              </div>
            ) : null}

            {/* Quality Passed Metrics Card */}
            {activeImage.qualityAssessment?.passed && (
              <div className="absolute bottom-16 inset-x-3 bg-white/90 backdrop-blur-md rounded border border-[#D1CDC2] p-2 shadow-md z-10">
                <div className="grid grid-cols-3 gap-1 text-[10px] font-mono-data text-[#3E4A3E]">
                  <div className="bg-[#D6E3D3]/50 p-1 rounded text-center">
                    <span>SHARPNESS: {activeImage.qualityAssessment.metrics.blurVariance > 120 ? "GOOD" : "OK"}</span>
                  </div>
                  <div className="bg-[#D6E3D3]/50 p-1 rounded text-center">
                    <span>LIGHT: {activeImage.qualityAssessment.metrics.meanBrightness}</span>
                  </div>
                  <div className="bg-[#D6E3D3]/50 p-1 rounded text-center">
                    <span>GLARE: {activeImage.qualityAssessment.metrics.glarePercentage < 0.08 ? "NONE" : "LOW"}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Action Bar for Existing Photo */}
            <div className="absolute bottom-3 inset-x-3 flex items-center justify-between gap-3 bg-[#1A1C1E]/80 backdrop-blur-md p-2 rounded-lg border border-white/20">
              <span className="text-white text-xs font-mono-data truncate pl-2">
                Slot {activeSlot.toUpperCase().replace("_", " ")}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleRemoveSlotImage(activeSlot)}
                  className="px-3 py-1.5 bg-red-600/80 hover:bg-red-600 text-white rounded text-xs font-mono-data flex items-center gap-1 active:scale-95 transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Remove</span>
                </button>
                <button
                  onClick={() => handleRemoveSlotImage(activeSlot)}
                  className="px-3 py-1.5 bg-[#4A5568] hover:bg-[#333E50] text-white rounded text-xs font-mono-data flex items-center gap-1 active:scale-95 transition-all"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Retake</span>
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* Live Camera Stream */
          <>
            <Webcam
              ref={webcamRef}
              audio={false}
              screenshotFormat="image/jpeg"
              videoConstraints={videoConstraints}
              onUserMediaError={(err) => {
                setCameraError(typeof err === "string" ? err : "Camera access unavailable");
              }}
              className="absolute inset-0 w-full h-full object-cover"
            />

            {/* Camera Error Fallback */}
            {cameraError && (
              <div className="absolute inset-0 bg-[#1A1C1E]/95 p-6 flex flex-col items-center justify-center text-center text-white z-20">
                <div className="w-12 h-12 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center mb-3">
                  <Camera className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-semibold mb-1">Camera Stream Inactive</h4>
                <p className="text-xs text-white/70 mb-4 max-w-xs font-mono-data">
                  {cameraError}. You can still upload packaged commodity photos directly.
                </p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 bg-[#4A5568] hover:bg-[#333E50] text-white rounded text-xs font-mono-data flex items-center gap-2"
                >
                  <Upload className="w-4 h-4" />
                  <span>Upload Label Photo</span>
                </button>
              </div>
            )}

            {/* Framing Guides Overlay (from Stitch) */}
            <div className="absolute inset-4 border border-[#D1CDC2]/40 rounded-sm pointer-events-none z-10">
              {/* Corner Brackets */}
              <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-[#BCC7DD]" />
              <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-[#BCC7DD]" />
              <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-[#BCC7DD]" />
              <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-[#BCC7DD]" />

              {/* Target PDP Box */}
              <div className="absolute inset-y-10 inset-x-8 border border-dashed border-[#BCC7DD]/60 flex items-center justify-center">
                <div className="absolute inset-0 bg-[#333E50]/5" />
                <div className="absolute top-2 left-2 flex items-center gap-1 bg-[#333E50]/60 backdrop-blur-sm px-1.5 py-0.5 rounded text-[10px] font-mono-data text-[#BCC7DD]">
                  <span>PDP TARGET</span>
                </div>
              </div>

              {/* Center Crosshairs Reticle */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-5 pointer-events-none">
                <div className="absolute top-1/2 left-0 w-full h-[1px] bg-[#BCC7DD]/80 -translate-y-1/2" />
                <div className="absolute left-1/2 top-0 h-full w-[1px] bg-[#BCC7DD]/80 -translate-x-1/2" />
              </div>
            </div>

            {/* Targeting Header Bar (Top of Viewfinder) */}
            <div className="absolute top-0 inset-x-0 bg-[#D6E3D3]/90 backdrop-blur-sm px-4 py-1.5 border-b border-[#BDCABA] flex items-center gap-2 shadow-sm z-10">
              <CheckCircle2 className="w-4 h-4 text-[#3E4A3E]" />
              <span className="font-mono-data text-[11px] font-semibold text-[#3E4A3E] tracking-wider">
                TARGETING: {activeSlot.toUpperCase().replace("_", " ")}
              </span>
            </div>

            {/* Alignment & Real-Time Quality Guidance Card (Bottom overlay) */}
            <div className="absolute bottom-3 inset-x-3 bg-white/95 backdrop-blur-md rounded border border-[#D1CDC2] p-2.5 shadow-lg z-10">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse" />
                  <span className="font-mono-data text-xs font-semibold text-[#1A1C1E]">
                    LIVE QUALITY GATE
                  </span>
                </div>
                <span className="font-mono-data text-[10px] text-[#75777D]">
                  TAP SHUTTER TO CAPTURE
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1 text-[10px] font-mono-data text-[#566155]">
                <div className="flex items-center gap-1 bg-[#F0EDE5] px-1.5 py-1 rounded">
                  <Check className="w-3 h-3 text-[#3E4A3E]" />
                  <span>ALIGN PDP</span>
                </div>
                <div className="flex items-center gap-1 bg-[#F0EDE5] px-1.5 py-1 rounded">
                  <Check className="w-3 h-3 text-[#3E4A3E]" />
                  <span>LEGIBILITY</span>
                </div>
                <div className="flex items-center gap-1 bg-[#F0EDE5] px-1.5 py-1 rounded">
                  <Check className="w-3 h-3 text-[#3E4A3E]" />
                  <span>BARCODE</span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Evidence Tray (Multi-Image Carousel) */}
      <div className="bg-[#F0EDE5] border-y border-[#D1CDC2] p-4 flex-1">
        <div className="flex items-center justify-between mb-2.5">
          <h3 className="font-mono-data text-xs font-semibold text-[#4A5568] tracking-wider uppercase">
            Evidence Index
          </h3>
          <span className="font-mono-data text-[11px] text-[#75777D]">
            {filledCount}/{requiredCount} REQUIRED
          </span>
        </div>

        <div className="flex gap-2.5 overflow-x-auto pb-1">
          {CAPTURE_SLOTS.map((slot) => {
            const img = images[slot.role];
            const isActive = activeSlot === slot.role;
            const hasQualityError = img && !img.qualityAssessment?.passed;

            return (
              <button
                key={slot.role}
                onClick={() => setActiveSlot(slot.role)}
                className={`relative shrink-0 w-24 aspect-square rounded-sm overflow-hidden flex flex-col items-center justify-center transition-all ${
                  isActive
                    ? "border-2 border-[#4A5568] shadow-md bg-white scale-[1.02]"
                    : "border border-[#D1CDC2] bg-[#F9F7F2] hover:bg-white"
                } ${hasQualityError ? "ring-2 ring-red-400" : ""}`}
              >
                {img ? (
                  <>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={img.dataUrl}
                      alt={slot.label}
                      className="absolute inset-0 w-full h-full object-cover"
                    />
                    <div className="absolute bottom-0 inset-x-0 bg-white/90 backdrop-blur-xs py-0.5 px-1 border-t border-[#D1CDC2] flex flex-col items-center">
                      <span className="font-mono-data text-[9px] font-bold text-[#1A1C1E]">
                        {slot.slotCode}
                      </span>
                      <span className="font-mono-data text-[8px] text-[#75777D] truncate w-full text-center">
                        {slot.label}
                      </span>
                    </div>
                    <div
                      className={`absolute top-1 right-1 w-4 h-4 rounded-full flex items-center justify-center border border-white ${
                        hasQualityError ? "bg-red-600 text-white" : "bg-[#3E4A3E] text-white"
                      }`}
                    >
                      {hasQualityError ? (
                        <AlertTriangle className="w-2.5 h-2.5" />
                      ) : (
                        <Check className="w-2.5 h-2.5" />
                      )}
                    </div>
                  </>
                ) : (
                  <div className="p-1 flex flex-col items-center justify-center text-center">
                    <Camera className="w-5 h-5 text-[#75777D] mb-1 opacity-70" />
                    <span className="font-mono-data text-[10px] font-semibold text-[#4A5568]">
                      {slot.slotCode}
                    </span>
                    <span className="font-mono-data text-[8px] text-[#75777D] leading-tight">
                      {slot.label}
                    </span>
                    <span
                      className={`absolute top-1 left-1 text-[8px] font-mono-data font-bold px-1 rounded ${
                        slot.isRequired
                          ? "bg-red-100 text-red-700"
                          : "bg-gray-200 text-gray-700"
                      }`}
                    >
                      {slot.isRequired ? "REQ" : "OPT"}
                    </span>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Controls Bar */}
      <div className="bg-[#F9F7F2] px-6 py-4 flex items-center justify-between border-t border-[#D1CDC2]">
        {/* Flash / Torch Toggle */}
        <button
          onClick={toggleTorch}
          aria-label="Toggle Flash"
          className={`w-12 h-12 rounded-full border border-[#D1CDC2] flex items-center justify-center transition-all active:scale-95 shadow-sm ${
            torchOn ? "bg-amber-100 text-amber-800" : "bg-[#F0EDE5] text-[#566155]"
          }`}
        >
          {torchOn ? (
            <Flashlight className="w-5 h-5" />
          ) : (
            <FlashlightOff className="w-5 h-5" />
          )}
        </button>

        {/* Central Shutter Button */}
        <div className="relative flex items-center justify-center">
          <div className="absolute -inset-1 rounded-full border-2 border-[#D1CDC2] pointer-events-none" />
          <button
            onClick={handleCapture}
            disabled={isCapturing || isAssessing || isQueueing}
            aria-label="Capture Photo"
            className={`w-16 h-16 rounded-full bg-[#4A5568] border-2 border-white flex items-center justify-center shadow-lg active:scale-95 transition-all group ${
              isCapturing ? "bg-[#333E50] scale-90" : "hover:bg-[#333E50]"
            }`}
          >
            <div className="w-12 h-12 rounded-full border-2 border-white/40 flex items-center justify-center">
              <Camera className="w-6 h-6 text-white group-active:scale-90 transition-transform" />
            </div>
          </button>
        </div>

        {/* Camera Flip or File Upload Fallback */}
        <div className="flex items-center gap-2">
          <button
            onClick={() =>
              setFacingMode((prev) => (prev === "environment" ? "user" : "environment"))
            }
            aria-label="Flip Camera"
            className="w-10 h-10 rounded-full border border-[#D1CDC2] bg-[#F0EDE5] flex items-center justify-center text-[#566155] shadow-sm hover:bg-white active:scale-95 transition-all"
          >
            <SwitchCamera className="w-4 h-4" />
          </button>

          <button
            onClick={() => fileInputRef.current?.click()}
            aria-label="Upload from Gallery"
            className="w-10 h-10 rounded-full border border-[#D1CDC2] bg-[#F0EDE5] flex items-center justify-center text-[#566155] shadow-sm hover:bg-white active:scale-95 transition-all"
          >
            <ImageIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Ready to Analyze / Queue Bottom Bar (CAP-07 Offline Queue) */}
      {isRequiredComplete && (
        <div className="bg-[#3E4A3E] text-white px-4 py-2.5 flex items-center justify-between shadow-md animate-in fade-in slide-in-from-bottom-2">
          <div className="flex items-center gap-2 text-xs font-mono-data">
            <CheckCheck className="w-4 h-4 text-emerald-300" />
            <span>Inspection Ready ({filledCount}/3)</span>
          </div>
          <button
            onClick={handleSaveAndQueue}
            disabled={isQueueing}
            className="px-3.5 py-1.5 bg-white text-[#3E4A3E] hover:bg-emerald-50 rounded font-mono-data text-xs font-bold shadow active:scale-95 transition-all flex items-center gap-1.5"
          >
            <CloudUpload className="w-3.5 h-3.5" />
            <span>{isQueueing ? "SAVING..." : "SAVE & QUEUE"}</span>
          </button>
        </div>
      )}

      {/* Bottom Navigation */}
      <nav className="sticky bottom-0 z-40 bg-[#F9F7F2]/90 backdrop-blur-md border-t border-[#D1CDC2] px-6 py-2 flex items-center justify-around">
        <button className="flex flex-col items-center gap-1 text-[#333E50] font-bold">
          <Camera className="w-5 h-5" />
          <span className="font-mono-data text-[10px] tracking-wider uppercase">
            Evidence
          </span>
        </button>

        <Link
          href="/history"
          className="flex flex-col items-center gap-1 text-[#75777D] hover:text-[#333E50] transition-colors relative"
        >
          <History className="w-5 h-5" />
          <span className="font-mono-data text-[10px] tracking-wider uppercase">
            History
          </span>
          {pendingCount > 0 && (
            <span className="absolute -top-1 right-2 w-4 h-4 rounded-full bg-[#BA1A1A] text-white text-[9px] font-mono-data flex items-center justify-center font-bold">
              {pendingCount}
            </span>
          )}
        </Link>

        <button
          onClick={() => setIsProfileOpen(true)}
          className="flex flex-col items-center gap-1 text-[#75777D] hover:text-[#333E50] transition-colors"
        >
          <Settings className="w-5 h-5" />
          <span className="font-mono-data text-[10px] tracking-wider uppercase">
            Settings
          </span>
        </button>
      </nav>

      {/* Officer Profile & Sandbox Persona Modal (E4-01 Government SSO) */}
      {isProfileOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#F9F7F2] rounded-xl border border-[#D1CDC2] shadow-2xl w-full max-w-sm overflow-hidden animate-in fade-in zoom-in-95">
            {/* Modal Header */}
            <div className="bg-[#333E50] text-white px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <div>
                  <h3 className="text-sm font-semibold leading-tight">MeriPehchan SSO</h3>
                  <p className="text-[10px] text-white/70 font-mono-data">National Single Sign-On (NSSO)</p>
                </div>
              </div>
              <button
                onClick={() => setIsProfileOpen(false)}
                className="text-white/70 hover:text-white p-1 rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Current Officer Status */}
            <div className="p-4 border-b border-[#D1CDC2] bg-white">
              <span className="text-[10px] font-mono-data text-[#75777D] uppercase tracking-wider block mb-1">
                Active Officer Session
              </span>
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-sm text-[#1A1C1E]">
                    {currentUser?.full_name || "Suresh Sharma (Default)"}
                  </div>
                  <div className="text-xs text-[#566155] font-mono-data">
                    {currentUser?.email || "suresh.sharma@gov.in"}
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono-data font-bold uppercase bg-[#D6E3D3] text-[#3E4A3E]">
                  {currentUser?.role || "OFFICER"}
                </span>
              </div>
            </div>

            {/* Quick Navigation Links */}
            <div className="p-4 space-y-2 border-b border-[#D1CDC2] bg-[#F5F2EA]">
              <span className="text-[10px] font-mono-data text-[#75777D] uppercase tracking-wider block mb-1">
                Portals & Dashboards
              </span>
              <div className="grid grid-cols-2 gap-2">
                <Link
                  href="/history"
                  onClick={() => setIsProfileOpen(false)}
                  className="flex items-center justify-between px-3 py-2 bg-white border border-[#D1CDC2] rounded-lg text-xs font-mono-data text-[#333E50] hover:bg-[#EAE7DC] transition-all"
                >
                  <span>History Feed</span>
                  <ExternalLink className="w-3 h-3 text-[#75777D]" />
                </Link>
                <Link
                  href="/dashboard"
                  onClick={() => setIsProfileOpen(false)}
                  className="flex items-center justify-between px-3 py-2 bg-white border border-[#D1CDC2] rounded-lg text-xs font-mono-data text-[#333E50] hover:bg-[#EAE7DC] transition-all"
                >
                  <span>Analytics</span>
                  <ExternalLink className="w-3 h-3 text-[#75777D]" />
                </Link>
                <Link
                  href="/admin/rule-packs"
                  onClick={() => setIsProfileOpen(false)}
                  className="col-span-2 flex items-center justify-between px-3 py-2 bg-white border border-[#D1CDC2] rounded-lg text-xs font-mono-data text-[#333E50] hover:bg-[#EAE7DC] transition-all"
                >
                  <span>Rule-Pack Management (Admin)</span>
                  <ExternalLink className="w-3 h-3 text-[#75777D]" />
                </Link>
              </div>
            </div>

            {/* Persona Switcher */}
            <div className="p-4 space-y-2.5">
              <span className="text-[10px] font-mono-data text-[#75777D] uppercase tracking-wider block">
                Switch Sandbox Persona (1-Click)
              </span>
              <div className="space-y-1.5">
                {[
                  {
                    id: "officer_suresh",
                    name: "Suresh Sharma",
                    role: "Field Officer (Delhi NCT)",
                    badge: "OFFICER",
                  },
                  {
                    id: "supervisor_priya",
                    name: "Priya Verma",
                    role: "Deputy Controller (Maharashtra)",
                    badge: "SUPERVISOR",
                  },
                  {
                    id: "admin_rajesh",
                    name: "Rajesh Gupta",
                    role: "Director & National Admin",
                    badge: "ADMIN",
                  },
                ].map((persona) => (
                  <button
                    key={persona.id}
                    disabled={isSwitchingPersona}
                    onClick={() => handleSwitchPersona(persona.id)}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-lg border border-[#D1CDC2] bg-white hover:bg-[#EAE7DC] active:scale-[0.99] transition-all text-left"
                  >
                    <div>
                      <div className="text-xs font-semibold text-[#1A1C1E]">{persona.name}</div>
                      <div className="text-[10px] text-[#75777D] font-mono-data">{persona.role}</div>
                    </div>
                    <span className="text-[9px] font-mono-data font-bold px-1.5 py-0.5 rounded bg-[#EAE7DC] text-[#4A5568]">
                      {persona.badge}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Close Button */}
            <div className="p-3 bg-[#EAE7DC] border-t border-[#D1CDC2] flex justify-end">
              <button
                onClick={() => setIsProfileOpen(false)}
                className="px-4 py-1.5 bg-[#4A5568] hover:bg-[#333E50] text-white rounded-lg text-xs font-mono-data font-bold transition-all"
              >
                CLOSE
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
