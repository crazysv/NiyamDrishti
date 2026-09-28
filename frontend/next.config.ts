import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Capacitor packages the generated `out/` directory inside the Android app.
  // Keep this browser-safe: the inspection API remains a separate HTTPS service.
  output: "export",
  images: {
    // The native bundle has no Next.js image optimizer server.
    unoptimized: true,
  },
  experimental: {
    // Stable one-worker export is more reliable on constrained development PCs
    // and produces the same static assets for Capacitor.
    cpus: 1,
  },
};

export default nextConfig;
