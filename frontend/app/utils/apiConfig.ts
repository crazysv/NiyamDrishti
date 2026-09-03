/**
 * Centralized API base URL configuration.
 * Normalizes NEXT_PUBLIC_API_URL so it reliably points to the versioned /api/v1 route.
 */
const rawUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").trim().replace(/\/+$/, "");

export const API_BASE = rawUrl.endsWith("/api/v1") ? rawUrl : `${rawUrl}/api/v1`;
