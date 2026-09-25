"use client";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/states";

export default function WorkbenchError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-10 md:px-8">
      <ErrorState title="This view could not be loaded">
        {error.message.includes("SAT-SA API") ? "The SAT-SA service returned an error or could not be reached." : "An unexpected error occurred."}
        {error.digest && <span className="mt-1 block font-mono text-[11.5px] text-muted">Reference {error.digest}</span>}
      </ErrorState>
      <Button className="mt-4" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
