import Image from "next/image";

/**
 * NiyamDrishti logo mark used in every screen header (top-left).
 * Uses next/image for automatic sharp rendering at the correct device pixel ratio.
 * Size matches the old "ND" avatar (w-8 h-8 = 32×32 logical px).
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
