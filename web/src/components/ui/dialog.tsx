"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Modal and drawer built on the native <dialog> element: focus is trapped,
 * Escape closes, and the rest of the page is inert while open.
 */
function useDialog(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    const handle = () => onClose();
    d.addEventListener("close", handle);
    return () => d.removeEventListener("close", handle);
  }, [onClose]);
  return ref;
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  const ref = useDialog(open, onClose);
  return (
    <dialog
      ref={ref}
      aria-labelledby="modal-title"
      className={cn(
        "m-auto w-[min(34rem,calc(100vw-2rem))] rounded-md border border-line bg-paper p-0 text-ink shadow-overlay backdrop:bg-ink/35 open:animate-rise",
        className,
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
        <div>
          <h2 id="modal-title" className="text-[16px] font-semibold">
            {title}
          </h2>
          {description && <div className="mt-1 text-[13px] text-muted">{description}</div>}
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="rounded-sm p-1 text-muted hover:bg-sunken hover:text-ink">
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>
      <div className="px-5 py-4">{children}</div>
      {footer && <div className="flex justify-end gap-2 border-t border-line bg-canvas px-5 py-3">{footer}</div>}
    </dialog>
  );
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  side = "right",
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  side?: "left" | "right";
  className?: string;
}) {
  const ref = useDialog(open, onClose);
  return (
    <dialog
      ref={ref}
      aria-label={title}
      className={cn(
        "fixed inset-y-0 m-0 h-dvh max-h-dvh w-[min(22rem,88vw)] border-line bg-paper p-0 text-ink shadow-overlay backdrop:bg-ink/35 open:animate-fade-in",
        side === "right" ? "right-0 left-auto border-l" : "left-0 border-r",
        className,
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {children}
    </dialog>
  );
}
