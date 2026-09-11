import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Connector } from "./Connector";
import { Odometer } from "./Odometer";
import { PulseDot } from "./PulseDot";

const BASE =
  "relative inline-flex w-fit min-w-0 shrink-0 cursor-pointer items-center justify-center whitespace-nowrap font-mono text-body-10 uppercase *:data-text:inline-flex *:data-text:h-48 *:data-text:items-center *:data-text:rounded-8 *:data-text:px-20 lg:*:data-text:px-24 *:data-connector:transition-colors *:data-text:transition-colors [--odometer-progress:0] motion-safe:hover:[--odometer-progress:1] disabled:pointer-events-none disabled:opacity-50 disabled:grayscale";

const VARIANTS = {
  dark: "*:data-text:bg-black *:data-connector:text-black *:data-text:text-white [&:hover_[data-connector]]:text-black-deep [&:hover_[data-text]]:bg-black-deep",
  light: "*:data-text:bg-ghost-grey *:data-connector:text-ghost-grey *:data-text:text-black [&:hover_[data-connector]]:text-white [&:hover_[data-text]]:bg-white",
} as const;

export type CaButtonVariant = keyof typeof VARIANTS;

interface CaButtonProps {
  /** First pill. When `rightText` is also set, the two pills are joined by a connector. */
  leftText?: string;
  rightText?: string;
  variant?: CaButtonVariant;
  showPulseDot?: boolean;
  href?: string;
  /** Open href in a new tab (external links). */
  external?: boolean;
  type?: "button" | "submit";
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
  children?: ReactNode;
  "aria-label"?: string;
}

/**
 * CA's split pill button: `[GET]=[ACCESS]•`. Each pill is a `data-text` span (48px tall, 8px
 * radius); hovering rolls every character through the Odometer.
 */
export function CaButton({
  leftText,
  rightText,
  variant = "dark",
  showPulseDot = false,
  href,
  external = false,
  type = "button",
  disabled,
  onClick,
  className,
  children,
  "aria-label": ariaLabel,
}: CaButtonProps) {
  const classes = cn(BASE, VARIANTS[variant], className);
  const content = (
    <>
      {leftText !== undefined ? (
        <span data-text="true">
          <Odometer text={leftText} />
        </span>
      ) : null}
      {children}
      {leftText !== undefined && rightText !== undefined ? <Connector orientation="vertical" length={26} /> : null}
      {rightText !== undefined ? (
        <span data-text="true">
          <Odometer text={rightText} />
        </span>
      ) : null}
      {showPulseDot ? <PulseDot className="absolute top-8 right-8" /> : null}
    </>
  );

  if (href) {
    return (
      <a
        href={href}
        className={classes}
        aria-label={ariaLabel}
        {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
      >
        {content}
      </a>
    );
  }
  return (
    <button type={type} disabled={disabled} onClick={onClick} className={classes} aria-label={ariaLabel}>
      {content}
    </button>
  );
}
