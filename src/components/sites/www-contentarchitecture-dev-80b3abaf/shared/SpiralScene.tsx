"use client";

import { cn } from "@/lib/utils";

export interface SpiralSceneProps {
  /** Text laid along the rings; a "." renders as a dot. CA: "THE CONTENT ARCHITECTURE." */
  phrase?: string;
  className?: string;
}

/**
 * STUB — replaced by the SpiralScene builder (WebGL2 rotating text rings with hover dissolve and
 * click-hold-release ripple). Renders the #232323 ground so the hero can be laid out.
 */
export function SpiralScene({ className }: SpiralSceneProps) {
  return <div aria-hidden="true" className={cn("relative size-full cursor-pointer select-none overflow-hidden bg-black", className)} />;
}
