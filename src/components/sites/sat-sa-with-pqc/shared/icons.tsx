import type { SVGProps } from "react";

export function ExternalLinkIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M6.5 4H4.6A1.6 1.6 0 0 0 3 5.6v5.8A1.6 1.6 0 0 0 4.6 13h5.8a1.6 1.6 0 0 0 1.6-1.6V9.5" />
      <path d="M9.5 3H13v3.5" />
      <path d="M13 3 7.2 8.8" />
    </svg>
  );
}

export function CheckIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M3.5 8.3 6.3 11l6.2-6.5" />
    </svg>
  );
}

export function DashIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" aria-hidden="true" {...props}>
      <path d="M4 8h8" />
    </svg>
  );
}
