"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { cn } from "@/lib/utils";
import { CaButton, type CaButtonVariant } from "./CaButton";

export interface EmailCaptureCopy {
  /** sr-only input label (CA: "Email"). */
  label: string;
  placeholder: string;
  /** Submit pill text; with `ctaRightText` the button becomes the split `[A]=[B]` pill. */
  ctaText: string;
  ctaRightText?: string;
  /** Shown under the form for 4s after a valid submit (CA: "You're on the list."). */
  successMessage: string;
  /** Shown under the form while the address is invalid (CA: "Enter a valid email address."). */
  errorMessage: string;
}

interface EmailCaptureProps {
  copy: EmailCaptureCopy;
  buttonVariant?: CaButtonVariant;
  /** Called after a valid submit (the popup closes itself 4s later). */
  onSuccess?: () => void;
  className?: string;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SUCCESS_MS = 4000;

type Status = { kind: "idle" } | { kind: "error" } | { kind: "success" };

/**
 * CA's `EmailCapture`: sr-only label, 48px mono input and a light pill submit, with the status
 * line absolutely positioned under the form. The clone has no backend — a valid address just
 * shows the success line (and sets the `tca-captured` session cookie the popup checks).
 */
export function EmailCapture({ copy, buttonVariant = "light", onSuccess, className }: EmailCaptureProps) {
  const inputId = useId();
  const messageId = useId();
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
    },
    [],
  );

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!EMAIL_PATTERN.test(email.trim())) {
      setStatus({ kind: "error" });
      return;
    }
    document.cookie = "tca-captured=1; path=/; SameSite=Lax";
    setStatus({ kind: "success" });
    onSuccess?.();
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      setStatus({ kind: "idle" });
      setEmail("");
    }, SUCCESS_MS);
  };

  const invalid = status.kind === "error";
  const message = status.kind === "error" ? copy.errorMessage : status.kind === "success" ? copy.successMessage : null;

  return (
    <form noValidate onSubmit={handleSubmit} className={cn("relative flex w-full min-w-0 flex-col", className)}>
      <input
        type="text"
        name="website"
        autoComplete="off"
        tabIndex={-1}
        aria-hidden="true"
        className="pointer-events-none absolute -left-[9999px] -z-1 h-px w-px overflow-hidden opacity-0"
      />
      <label htmlFor={inputId} className="sr-only">
        {copy.label}
      </label>
      <div className="flex gap-4 lg:flex-row">
        <input
          id={inputId}
          type="email"
          name="email"
          autoComplete="email"
          placeholder={copy.placeholder}
          value={email}
          aria-invalid={invalid}
          aria-describedby={message ? messageId : undefined}
          onChange={(event) => {
            setEmail(event.target.value);
            if (status.kind === "error") setStatus({ kind: "idle" });
          }}
          className="h-48 min-w-0 rounded-8 border border-current/20 px-16 font-mono text-body-10 text-current outline-none transition-colors placeholder:text-current/40 focus-visible:border-current/60 enabled:hover:border-current/60 disabled:cursor-not-allowed disabled:opacity-50 bg-black lg:flex-1"
        />
        <CaButton
          type="submit"
          variant={buttonVariant}
          leftText={copy.ctaText}
          rightText={copy.ctaRightText}
          className="shrink-0"
        />
      </div>
      {message ? (
        <p
          id={messageId}
          role={invalid ? "alert" : "status"}
          className={cn("pointer-events-none absolute top-full left-0 mt-8 font-mono text-ui", invalid && "text-[#dc2626]")}
        >
          {message}
        </p>
      ) : null}
    </form>
  );
}
