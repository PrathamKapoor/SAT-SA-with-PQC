import type { SVGProps } from "react";

export function ShieldMark(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
      <path
        d="M12 2.5 20 6v6c0 5-3.5 8.5-8 9.5C7.5 20.5 4 17 4 12V6l8-3.5Z"
        className="fill-primary/15 stroke-primary"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M8.5 12.3 11 14.8 15.5 9.8"
        className="stroke-primary"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
