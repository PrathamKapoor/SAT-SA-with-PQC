import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "attention" | "quiet";
type Size = "sm" | "md" | "lg";

const base =
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap font-medium transition-colors duration-150 disabled:pointer-events-none disabled:opacity-45 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

const variants: Record<Variant, string> = {
  primary: "bg-ink text-white hover:bg-ink-2",
  secondary: "border border-line-2 bg-paper text-ink hover:border-ink/40 hover:bg-canvas",
  ghost: "text-ink-2 hover:bg-sunken hover:text-ink",
  attention: "bg-attention text-white hover:bg-attention-strong",
  quiet: "text-brand hover:text-brand-strong underline-offset-4 hover:underline",
};

const sizes: Record<Size, string> = {
  sm: "h-7 rounded-sm px-2.5 text-[12.5px]",
  md: "h-9 rounded-sm px-3.5 text-[13.5px]",
  lg: "h-11 rounded-md px-5 text-[14.5px]",
};

export function buttonClass(variant: Variant = "secondary", size: Size = "md", className?: string) {
  return cn(base, variants[variant], variant === "quiet" ? "h-auto px-0" : sizes[size], className);
}

export function Button({
  variant,
  size,
  className,
  ...props
}: ComponentProps<"button"> & { variant?: Variant; size?: Size }) {
  return <button type="button" className={buttonClass(variant, size, className)} {...props} />;
}

export function ButtonLink({
  variant,
  size,
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: Variant; size?: Size; children: ReactNode }) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}

/** Icon-only control: requires a label, which is also used as the tooltip. */
export function IconButton({
  label,
  className,
  children,
  ...props
}: ComponentProps<"button"> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex size-8 items-center justify-center rounded-sm text-muted transition-colors hover:bg-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-brand",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
