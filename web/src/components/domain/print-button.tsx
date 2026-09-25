"use client";

import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";

export function PrintButton({ disabled, reason }: { disabled?: boolean; reason?: string }) {
  return (
    <Button variant="primary" onClick={() => window.print()} disabled={disabled} title={disabled ? reason : "Print or save as PDF"} className="no-print">
      <Printer className="size-4" aria-hidden="true" />
      Print report
    </Button>
  );
}
