"use client";

import { useRef, type ReactNode } from "react";
import { useInView } from "./hooks";

interface DeferredMountProps {
  children: ReactNode;
  /** Rendered until the wrapper comes within `releaseMargin` of the viewport. */
  placeholder?: ReactNode;
  /** IntersectionObserver rootMargin for mounting (CA uses "100%"). */
  releaseMargin?: string;
  className?: string;
}

/** Mounts expensive children (WebGL scenes, IDE) only once they approach the viewport. */
export function DeferredMount({ children, placeholder = null, releaseMargin = "100%", className }: DeferredMountProps) {
  const ref = useRef<HTMLDivElement>(null);
  const near = useInView(ref, { rootMargin: releaseMargin });
  return (
    <div ref={ref} className={className ?? "size-full"}>
      {near ? children : placeholder}
    </div>
  );
}
