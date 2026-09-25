import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Page header: technical eyebrow, confident title, optional actions. */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-end justify-between gap-x-8 gap-y-4 pb-6", className)}>
      <div className="min-w-0 max-w-3xl">
        {eyebrow && <p className="label mb-2">{eyebrow}</p>}
        <h1 className="text-[28px] leading-[1.1] font-semibold tracking-[-0.02em] text-ink md:text-[32px]">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-muted">{description}</p>}
        {meta && <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

/** Section heading inside a page. Uses a hairline, not a box. */
export function SectionHeader({
  title,
  label,
  aside,
  id,
  className,
  as: As = "h2",
}: {
  title: ReactNode;
  label?: ReactNode;
  aside?: ReactNode;
  id?: string;
  className?: string;
  as?: "h2" | "h3";
}) {
  return (
    <div className={cn("flex items-baseline justify-between gap-4 pb-3", className)}>
      <div className="flex min-w-0 items-baseline gap-3">
        {label && <span className="label shrink-0">{label}</span>}
        <As id={id} className="truncate text-[15px] font-semibold tracking-[-0.01em] text-ink">
          {title}
        </As>
      </div>
      {aside && <div className="shrink-0 text-[12.5px] text-muted">{aside}</div>}
    </div>
  );
}

/** A bordered surface. Used sparingly: most content sits on hairline rules. */
export function Panel({ className, children, as: As = "section", ...rest }: { className?: string; children: ReactNode; as?: "section" | "div" | "article" | "aside"; "aria-labelledby"?: string; "aria-label"?: string }) {
  return (
    <As className={cn("rounded-md border border-line bg-paper", className)} {...rest}>
      {children}
    </As>
  );
}

export function Metric({
  label,
  value,
  unit,
  detail,
  tone = "ink",
  size = "md",
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  detail?: ReactNode;
  tone?: "ink" | "brand" | "attention" | "critical" | "info";
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const color = { ink: "text-ink", brand: "text-brand", attention: "text-attention", critical: "text-critical", info: "text-info" }[tone];
  const scale = { sm: "text-[20px]", md: "text-[28px]", lg: "text-[40px]" }[size];
  return (
    <div className={cn("min-w-0", className)}>
      <dt className="label truncate">{label}</dt>
      <dd className="mt-1 flex items-baseline gap-1">
        <span className={cn("num leading-none font-semibold tracking-[-0.03em]", scale, color)}>{value}</span>
        {unit && <span className="text-[13px] text-muted">{unit}</span>}
      </dd>
      {detail && <dd className="mt-1 truncate text-[12.5px] text-muted">{detail}</dd>}
    </div>
  );
}

export function KeyValue({ items, className, columns = 2 }: { items: Array<[ReactNode, ReactNode]>; className?: string; columns?: 1 | 2 | 3 | 4 }) {
  const cols = { 1: "grid-cols-1", 2: "grid-cols-1 sm:grid-cols-2", 3: "grid-cols-2 lg:grid-cols-3", 4: "grid-cols-2 lg:grid-cols-4" }[columns];
  return (
    <dl className={cn("grid gap-x-6 gap-y-3", cols, className)}>
      {items.map(([k, v], i) => (
        <div key={i} className="min-w-0">
          <dt className="label">{k}</dt>
          <dd className="mt-0.5 truncate text-[13.5px] text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
