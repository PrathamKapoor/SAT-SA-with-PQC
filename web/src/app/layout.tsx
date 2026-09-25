import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

// next/font self-hosts these at build time: no runtime font CDN request.
const fontSans = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });
const fontMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  title: { template: "%s · SAT-SA", default: "SAT-SA · Supervisory Analytics for SOC Assessment" },
  description:
    "A periodic, offline, evidence-driven supervisory analytics system that supports human examiners, with post-quantum verifiable evidence (TRUST-SAT).",
};

export const viewport: Viewport = { themeColor: "#ffffff", colorScheme: "light" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${fontSans.variable} ${fontMono.variable}`}>
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
