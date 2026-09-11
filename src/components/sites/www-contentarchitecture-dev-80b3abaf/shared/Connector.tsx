import { cn } from "@/lib/utils";

const PATHS = {
  vertical: {
    start: 'path("M0 0H1C1 1.1046 1.8954 2 3 2C4.1046 2 5 1.1046 5 0H6V4H0Z")',
    end: 'path("M0 0H6V4H5C5 2.8954 4.1046 2 3 2C1.8954 2 1 2.8954 1 4H0Z")',
  },
  horizontal: {
    start: 'path("M0 0H4V6H0V5C1.1046 5 2 4.1046 2 3C2 1.8954 1.1046 1 0 1Z")',
    end: 'path("M0 0H4V1C2.8954 1 2 1.8954 2 3C2 4.1046 2.8954 5 4 5V6H0Z")',
  },
} as const;

interface ConnectorProps {
  orientation?: "vertical" | "horizontal";
  /** Length in px along the connector axis (CA uses 26 between buttons, 28 under labels). */
  length: number;
  className?: string;
}

/**
 * The 6px "bridge" that joins two CA pills/cards: a bar with concave semicircle caps.
 * Coloured with `bg-current`, so set `text-*` on it (or `*:data-connector:text-*` on a parent).
 */
export function Connector({ orientation = "vertical", length, className }: ConnectorProps) {
  const vertical = orientation === "vertical";
  const paths = PATHS[orientation];
  return (
    <div
      aria-hidden="true"
      data-connector="true"
      className={cn("flex", vertical ? "-mx-px w-6 flex-col" : "-my-px h-6 flex-row", className)}
      style={vertical ? { height: length } : { width: length }}
    >
      <div
        className={cn("shrink-0 bg-current", vertical ? "h-4 w-full" : "h-full w-4")}
        style={{ clipPath: paths.start }}
      />
      <div className={cn("grow bg-current", vertical ? "-my-px w-full" : "-mx-px h-full")} />
      <div
        className={cn("shrink-0 bg-current", vertical ? "h-4 w-full" : "h-full w-4")}
        style={{ clipPath: paths.end }}
      />
    </div>
  );
}
