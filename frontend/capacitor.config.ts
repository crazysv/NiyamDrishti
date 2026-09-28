import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  // This identifies the student project without implying a government-issued app.
  appId: "com.niyamdrishti.app",
  appName: "NiyamDrishti",
  webDir: "out",
  android: {
    // Use HTTPS for every deployed API call. Clear-text traffic is never needed.
    allowMixedContent: false,
  },
};

export default config;
