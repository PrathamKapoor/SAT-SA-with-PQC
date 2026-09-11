import type { SVGProps } from "react";

export function LogoMark(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
      <rect x="2" y="2" width="20" height="20" rx="5" className="fill-tertiary" />
      <path
        d="M8 15.5V8.5L12 12L16 8.5V15.5"
        stroke="currentColor"
        className="text-tertiary-foreground"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
