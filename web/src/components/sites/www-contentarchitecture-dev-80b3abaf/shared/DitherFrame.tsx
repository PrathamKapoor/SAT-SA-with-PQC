"use client";

import { useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface DitherFrameProps {
  /** Title-bar label (uppercase mono, white/40). Omit for a frame without a title bar. */
  title?: ReactNode;
  /** Extra content on the right of the title bar. */
  titleRight?: ReactNode;
  /** Title bar acts as a drag handle; a dashed outline marks the origin while displaced. */
  draggable?: boolean;
  children: ReactNode;
  className?: string;
  /** Classes for the inner black window. */
  innerClassName?: string;
}

/**
 * CA framed window: black-deep frame (p-6 / lg:p-8) with a 4px dithered checker, shadow-lg,
 * around an inner `bg-black rounded-4 ring-1 ring-white/10` window with a 26px title bar.
 */
export function DitherFrame({ title, titleRight, draggable = false, children, className, innerClassName }: DitherFrameProps) {
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const drag = useRef<{ startX: number; startY: number; baseX: number; baseY: number } | null>(null);

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!draggable) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { startX: e.clientX, startY: e.clientY, baseX: offset.x, baseY: offset.y };
  };
  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d) return;
    setOffset({ x: d.baseX + e.clientX - d.startX, y: d.baseY + e.clientY - d.startY });
  };
  const onPointerUp = () => {
    drag.current = null;
  };

  const displaced = offset.x !== 0 || offset.y !== 0;

  return (
    <div className={cn("relative", className)}>
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute inset-0 rounded-8 border border-current/30 border-dashed transition-opacity",
          displaced ? "opacity-100" : "opacity-0",
        )}
      />
      <div className="relative" style={displaced ? { transform: `translate(${offset.x}px, ${offset.y}px)` } : undefined}>
        <div className="rounded-8 bg-black-deep bg-dither p-6 shadow-lg ring ring-black-deep transition-colors duration-300 lg:p-8">
          <div
            className={cn(
              "isolate flex flex-col overflow-hidden rounded-4 bg-black font-mono text-caption-10 text-white ring-1 ring-white/10",
              innerClassName,
            )}
          >
            {title !== undefined ? (
              <div
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onPointerCancel={onPointerUp}
                className={cn(
                  "flex h-26 items-center justify-between border-white/10 border-b px-16",
                  draggable && "cursor-grab touch-none select-none active:cursor-grabbing",
                )}
              >
                <span className="text-white/40 uppercase tracking-wide">{title}</span>
                {titleRight}
              </div>
            ) : null}
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
