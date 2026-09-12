"use client";

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { EmailCapture, type EmailCaptureCopy } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/EmailCapture";
import { usePrefersReducedMotion } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";
import { usePresence } from "./ReadmeDrawer";

export interface FloatingCaptureContent {
  title: string;
  text: string;
  /** aria-label of the X button (CA: "Close"). */
  closeLabel: string;
  form: EmailCaptureCopy;
  /** Seconds after load before the popup appears (CA: 12). */
  delaySeconds: number;
  /** Desktop corner: 48px from the left or right edge. */
  side: "left" | "right";
  /** Also open when the pointer leaves the document (CA: false). */
  exitIntent?: boolean;
}

const PROMPT_COOKIE = "tca-prompt-site";
const CAPTURED_COOKIE = "tca-captured";
const CLOSE_AFTER_SUCCESS_MS = 4000;

const CLOSE_BUTTON =
  "inline-flex w-fit min-w-0 shrink-0 cursor-pointer items-end whitespace-nowrap font-mono text-caption-10 uppercase [--odometer-progress:0] motion-safe:hover:[--odometer-progress:1] disabled:pointer-events-none disabled:opacity-50 disabled:grayscale *:data-label:inline-flex *:data-label:items-center *:data-label:justify-center *:data-label:rounded-4 *:data-icon:inline-flex *:data-icon:items-center *:data-icon:justify-center *:data-icon:rounded-4 *:data-connector:transition-colors *:data-icon:transition-colors *:data-label:transition-colors *:data-icon:size-32 *:data-label:h-18 *:data-connector:w-32 *:data-label:px-6 *:data-icon:bg-ghost-grey *:data-label:bg-ghost-grey *:data-connector:text-ghost-grey *:data-icon:text-black *:data-label:text-black [&:hover_[data-connector]]:text-white [&:hover_[data-icon]]:bg-white [&:hover_[data-label]]:bg-white flex-col-reverse -mt-4 -mr-4";

function hasCookie(name: string) {
  return document.cookie.split(";").some((part) => part.trim().startsWith(`${name}=1`));
}

/**
 * Newsletter popup: once per browser session, `delaySeconds` after load (optionally on exit
 * intent), unless the `tca-prompt-site` / `tca-captured` session cookies exist. Esc or X closes
 * it; a successful subscribe closes it 4s later. Enters from 24px below (500ms ease-out), exits
 * back down (350ms ease-in-out).
 */
export function FloatingCapture({ content }: { content: FloatingCaptureContent }) {
  const { title, text, closeLabel, form, delaySeconds, side, exitIntent = false } = content;
  const titleId = useId();
  const reduced = usePrefersReducedMotion();
  const [open, setOpen] = useState(false);
  const { present, visible } = usePresence(open, reduced ? 10 : 350);
  const shownRef = useRef(false);
  const closeTimer = useRef<number | null>(null);

  useEffect(() => {
    if (hasCookie(PROMPT_COOKIE) || hasCookie(CAPTURED_COOKIE)) return;
    const show = () => {
      if (shownRef.current || hasCookie(PROMPT_COOKIE) || hasCookie(CAPTURED_COOKIE)) return;
      shownRef.current = true;
      document.cookie = `${PROMPT_COOKIE}=1; path=/; SameSite=Lax`;
      setOpen(true);
    };
    const timer = window.setTimeout(show, delaySeconds * 1000);
    const root = document.documentElement;
    if (exitIntent) root.addEventListener("mouseleave", show);
    return () => {
      window.clearTimeout(timer);
      if (exitIntent) root.removeEventListener("mouseleave", show);
    };
  }, [delaySeconds, exitIntent]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  useEffect(
    () => () => {
      if (closeTimer.current) window.clearTimeout(closeTimer.current);
    },
    [],
  );

  const handleSuccess = () => {
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(false), CLOSE_AFTER_SUCCESS_MS);
  };

  if (!present) return null;

  return createPortal(
    <div
      role="dialog"
      aria-label={title}
      className={cn(
        "fixed inset-x-16 bottom-16 z-50 lg:inset-x-auto lg:bottom-48 lg:w-520",
        side === "left" ? "lg:left-48" : "lg:right-48",
        "transition-[opacity,transform] motion-reduce:duration-10",
        visible ? "translate-y-0 opacity-100 duration-500 ease-out" : "translate-y-24 opacity-0 duration-350 ease-in-out",
      )}
    >
      <section
        aria-labelledby={titleId}
        className="flex flex-col gap-16 rounded-8 p-16 lg:gap-24 lg:p-32 border border-white/20 bg-black text-white shadow-2xl"
      >
        <div className="grid gap-16">
          <div className="flex flex-col gap-8">
            <div className="flex items-start justify-between gap-16">
              <p id={titleId} className="text-balance font-medium text-body-30">
                {title}
              </p>
              <button type="button" aria-label={closeLabel} className={CLOSE_BUTTON} onClick={() => setOpen(false)}>
                <span data-icon="true">X</span>
              </button>
            </div>
            <p className="text-pretty text-body-10 text-ghost-grey">{text}</p>
          </div>
          <EmailCapture copy={form} buttonVariant="light" onSuccess={handleSuccess} />
        </div>
      </section>
    </div>,
    document.body,
  );
}
