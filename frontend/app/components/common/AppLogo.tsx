import Image from "next/image";

/**
 * Shared NiyamDrishti logo mark — used in every screen header (top-left).
 * next/image serves the right resolution for each device pixel ratio automatically.
 * Replaces the old "ND" text avatar (w-8 h-8 = 32×32 logical px).
 */
export default function AppLogo({ size = 32 }: { size?: number }) {
  return (
    <Image
      src="/icon-192.png"
      alt="NiyamDrishti logo"
      width={size}
      height={size}
      priority
      style={{
        borderRadius: 6,
        display: "block",
        imageRendering: "crisp-edges",
      }}
    />
  );
}
