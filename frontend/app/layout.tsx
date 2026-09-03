import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import ColdStartBanner from "@/app/components/common/ColdStartBanner";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "NiyamDrishti — Legal Metrology Compliance Platform",
  description:
    "Automated, evidence-backed inspection system for Legal Metrology (Packaged Commodities) Rules, 2011",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[#F9F7F2] text-[#1A1C1E]">
        <ColdStartBanner />
        {children}
      </body>
    </html>
  );
}
