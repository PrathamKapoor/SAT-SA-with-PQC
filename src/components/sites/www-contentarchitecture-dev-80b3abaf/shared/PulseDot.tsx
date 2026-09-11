import { cn } from "@/lib/utils";

interface PulseDotProps {
  /** Tailwind size utility, e.g. "size-6" (default). */
  size?: string;
  className?: string;
}

/** Orange status dot with an expanding ping ring (statusPing 1.8s). */
export function PulseDot({ size = "size-6", className }: PulseDotProps) {
  return (
    <span aria-hidden="true" className={cn("flex", size, className)}>
      <span className={cn("absolute inline-flex animate-status-ping rounded-full bg-accent motion-reduce:hidden", size)} />
      <span className={cn("relative inline-flex rounded-full bg-accent", size)} />
    </span>
  );
}
