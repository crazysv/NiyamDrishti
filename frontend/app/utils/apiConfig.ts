/**
 * Centralized API base URL configuration.
 * Normalizes NEXT_PUBLIC_API_URL so it reliably points to the versioned /api/v1 route.
 * Automatically targets the live production Render backend when accessed from remote deployments (Vercel, Cloudflare Pages),
 * while preserving localhost:8000 for local development.
 */

function resolveBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;

  // `next build` can load a developer's .env.local, where the API points at
  // localhost:8000. In a Capacitor APK, localhost is the phone itself—not this
  // development computer—so never use a localhost environment URL there.
  if (Capacitor.isNativePlatform()) {
    if (!envUrl || envUrl.includes("localhost") || envUrl.includes("127.0.0.1")) {
      return "https://niyamdrishti-api.onrender.com";
    }
    return envUrl;
  }

  // In the browser, if deployed on any remote domain (Vercel, Cloudflare, custom domain)
  // and envUrl is either not set or set to localhost, fallback to live Render backend
  if (typeof window !== "undefined") {
    const isLocalhost =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1";

    if (!isLocalhost && (!envUrl || envUrl.includes("localhost") || envUrl.includes("127.0.0.1"))) {
      return "https://niyamdrishti-api.onrender.com";
    }
  }

  // If set to an explicit production URL, use it
  if (envUrl && envUrl.trim()) {
    return envUrl.trim();
  }

  return "https://niyamdrishti-api.onrender.com";
}

const rawUrl = resolveBaseUrl().replace(/\/+$/, "");

export const API_BASE = rawUrl.endsWith("/api/v1") ? rawUrl : `${rawUrl}/api/v1`;
import { Capacitor } from "@capacitor/core";
