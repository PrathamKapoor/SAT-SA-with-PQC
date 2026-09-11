"use client";

import type { RefObject } from "react";
import { cn } from "@/lib/utils";
import { useIsTouchDevice } from "./hooks";

interface CursorLabelProps {
  /** Positioned imperatively by `setupCursorTracking` (left/top = local pointer position). */
  labelRef: RefObject<HTMLDivElement | null>;
  isHovering: boolean;
  text?: string;
}

/**
 * White mono tag that trails the pointer (offset 20px) inside a WebGL scene. On touch devices it
 * is pinned to the top-right corner instead.
 */
export function CursorLabel({ labelRef, isHovering, text = "Click" }: CursorLabelProps) {
  const touch = useIsTouchDevice();
  if (touch) {
    return (
      <div aria-hidden="true" className="pointer-events-none absolute top-16 right-16 z-2 select-none whitespace-nowrap bg-white p-2 font-mono text-black text-caption-10 uppercase">
        {text}
      </div>
    );
  }
  return (
    <div
      ref={labelRef}
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute top-0 left-0 z-2 translate-x-20 translate-y-20 select-none whitespace-nowrap bg-white p-2 font-mono text-black text-caption-10 uppercase transition-opacity duration-150",
        isHovering ? "opacity-100" : "opacity-0",
      )}
    >
      {text}
    </div>
  );
}

interface CursorTrackingOptions {
  container: HTMLElement;
  signal: AbortSignal;
  labelRef: RefObject<HTMLDivElement | null>;
  setIsHovering: (hovering: boolean) => void;
  onPointerMove?: (x: number, y: number) => void;
  onPointerEnter?: (x: number, y: number) => void;
  onPointerLeave?: () => void;
  onPointerDown?: (x: number, y: number) => void;
  onPointerUp?: (x: number, y: number) => void;
  onClick?: (x: number, y: number) => void;
}

/** Wires pointer events on `container` (container-local coordinates) and moves the label. */
export function setupCursorTracking({
  container,
  signal,
  labelRef,
  setIsHovering,
  onPointerMove,
  onPointerEnter,
  onPointerLeave,
  onPointerDown,
  onPointerUp,
  onClick,
}: CursorTrackingOptions) {
  const local = (e: PointerEvent | MouseEvent) => {
    const rect = container.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };
  const moveLabel = (x: number, y: number) => {
    const label = labelRef.current;
    if (!label) return;
    label.style.left = `${x}px`;
    label.style.top = `${y}px`;
  };
  const leave = () => {
    onPointerLeave?.();
    setIsHovering(false);
  };
  container.addEventListener(
    "pointermove",
    (e) => {
      const { x, y } = local(e);
      moveLabel(x, y);
      onPointerMove?.(x, y);
    },
    { passive: true, signal },
  );
  container.addEventListener(
    "pointerenter",
    (e) => {
      const { x, y } = local(e);
      moveLabel(x, y);
      onPointerEnter?.(x, y);
      setIsHovering(true);
    },
    { signal },
  );
  container.addEventListener("pointerleave", leave, { signal });
  container.addEventListener("pointercancel", leave, { signal });
  container.addEventListener(
    "pointerdown",
    (e) => {
      const { x, y } = local(e);
      onPointerDown?.(x, y);
    },
    { signal },
  );
  container.addEventListener(
    "pointerup",
    (e) => {
      const { x, y } = local(e);
      onPointerUp?.(x, y);
    },
    { signal },
  );
  container.addEventListener(
    "click",
    (e) => {
      const { x, y } = local(e);
      onClick?.(x, y);
    },
    { signal },
  );
}
