"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";
import { useLenis } from "lenis/react";

interface BiosLine {
  text: string;
  className?: string;
}

const BIOS_LINES: BiosLine[] = [
  { text: "BIOS Date: 04/01/2024  22:09:51  Ver: 1.0.B3" },
  { text: "The Content Architecture Web Core(tm) CPU @ 3.40GHz", className: "text-white" },
  { text: "Speed: 3400 MHz" },
  { text: " " },
  { text: "Press DEL to run Setup,  F11 for Boot Menu", className: "text-[#54fcfc]" },
  { text: "Initializing USB Controllers ..  Done.", className: "text-[#54fcfc]" },
  { text: "65536MB OK", className: "text-white" },
  { text: " " },
  { text: "Auto-Detecting SATA drives ..." },
  { text: "  SATA Port0 : None" },
  { text: "  SATA Port1 : None" },
  { text: "  SATA Port2 : None" },
  { text: "  SATA Port3 : None" },
  { text: " " },
  { text: "Reboot and Select proper Boot device" },
  { text: "or Insert Boot Media in selected Boot device and press a key" },
];

const SCANLINES = {
  opacity: 0.06,
  backgroundImage:
    "repeating-linear-gradient(rgb(255,255,255) 0px,rgb(255,255,255) 1px,transparent 1px,transparent 3px)",
};

/** Full-screen BIOS easter egg shown after `rm -rf /`. Any key or pointer press reloads the page. */
export function CrashScreen() {
  const lenis = useLenis();

  useEffect(() => {
    if (!lenis) return;
    lenis.stop();
    return () => lenis.start();
  }, [lenis]);

  useEffect(() => {
    const reboot = () => window.location.reload();
    window.addEventListener("keydown", reboot);
    window.addEventListener("pointerdown", reboot);
    return () => {
      window.removeEventListener("keydown", reboot);
      window.removeEventListener("pointerdown", reboot);
    };
  }, []);

  return createPortal(
    <div
      role="alert"
      aria-label="System BIOS (easter egg). No real files were touched. Press any key to reboot the page."
      className="fixed inset-0 z-10000 flex animate-fade-in cursor-pointer flex-col bg-[#0000a8] font-mono text-[#c6c6c6] text-caption-10 selection:bg-[#d4d4d4] selection:text-[#0000a8]"
    >
      <div aria-hidden="true" className="pointer-events-none absolute inset-0" style={SCANLINES} />
      <div className="relative flex shrink-0 items-center justify-between gap-12 bg-[#a8a8a8] px-16 py-4 font-semibold text-[#000080]">
        <span>AMIBIOS(C)2024 American Megatrends, Inc.</span>
        <span className="hidden sm:inline">v1.0.B3</span>
      </div>
      <div className="relative flex min-h-0 flex-1 flex-col overflow-auto px-16 py-16 sm:px-40 sm:py-24">
        <div className="wrap-break-word whitespace-pre-wrap">
          {BIOS_LINES.map((line, i) => (
            <div key={i} className={line.className}>
              {line.text}
            </div>
          ))}
        </div>
      </div>
      <div className="relative flex shrink-0 items-center justify-between gap-12 bg-[#a8a8a8] px-16 py-4 text-[#000080]">
        <span className="flex items-center gap-8 font-semibold">
          <span>Press any key to reboot</span>
          <span aria-hidden="true" className="inline-block h-14 w-8 animate-cursor-blink bg-[#000080] align-middle" />
        </span>
        <span className="hidden font-semibold sm:inline">F1: Setup &nbsp; ESC: Boot Menu</span>
      </div>
    </div>,
    document.body,
  );
}
