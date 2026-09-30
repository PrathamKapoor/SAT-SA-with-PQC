import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./landing.css";

// The landing page has its own root layout and stylesheet: its design tokens
// (1px spacing unit, caption/body/headline type scale) share class names with
// the workbench's, so each root layout loads only its own CSS. Navigating
// between the two is a full page load.
const fontSans = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });
const fontMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  title: "TRUST-SAT: Supervisory Analytics Tool for SOC Assessment",
  description:
    "A periodic, offline, evidence-driven supervisory analytics system supporting human examiners, with post-quantum trusted evidence (TRUST-SAT).",
};

export const viewport: Viewport = { themeColor: "#ffffff", colorScheme: "light" };

export default function LandingLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${fontSans.variable} ${fontMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
