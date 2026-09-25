"use client";

import { EvidenceFieldCanvas } from "./EvidenceFieldCanvas";

/** The evidence field on the sign-in panel, shown organised; hover reveals each record. */
export function LoginVisual() {
  return (
    <EvidenceFieldCanvas
      className="absolute inset-x-6 top-24 bottom-40"
      density="medium"
      initial={1}
      label="Illustration: SOC evidence records organised into findings for supervisory review."
    />
  );
}
