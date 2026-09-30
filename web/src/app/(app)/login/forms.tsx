"use client";

import { AlertCircle, ArrowRight, KeyRound, Loader2 } from "lucide-react";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { buttonClass } from "@/components/ui/button";
import { signInWithCredential, type SignInState } from "@/lib/auth/actions";
import { cn } from "@/lib/utils";

function Submit({ children }: { children: React.ReactNode }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending} aria-disabled={pending} className={buttonClass("primary", "lg", "w-full")}>
      {pending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
      {pending ? "Verifying" : children}
    </button>
  );
}

/** Credential sign-in against the SAT-SA service. */
export function CredentialForm({ configured }: { configured: boolean }) {
  const [state, action] = useActionState<SignInState, FormData>(signInWithCredential, { error: null });
  return (
    <form action={action} className="mt-8 space-y-4" noValidate>
      <div>
        <label htmlFor="credential" className="block text-[13px] font-medium text-ink">
          Issued credential
        </label>
        <div className="relative mt-1.5">
          <KeyRound className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-faint" aria-hidden="true" />
          <input
            id="credential"
            name="credential"
            type="password"
            autoComplete="current-password"
            spellCheck={false}
            required
            aria-invalid={state.error ? true : undefined}
            aria-describedby={state.error ? "credential-error" : "credential-hint"}
            placeholder="key_id.secret"
            className={cn(
              "h-11 w-full rounded-md border bg-paper pr-3 pl-9 font-mono text-[13.5px] text-ink placeholder:text-faint focus:border-brand focus:ring-2 focus:ring-brand/20 focus:outline-none",
              state.error ? "border-critical" : "border-line-2",
            )}
          />
        </div>
        {state.error ? (
          <p id="credential-error" role="alert" className="mt-2 flex items-start gap-1.5 text-[12.5px] text-critical">
            <AlertCircle className="mt-px size-3.5 shrink-0" aria-hidden="true" />
            {state.error}
          </p>
        ) : (
          <p id="credential-hint" className="mt-2 text-[12px] text-muted">
            {configured ? "Format key_id.secret, as shown once when the credential was issued." : "This deployment has no SAT-SA service configured (SATSA_API_BASE_URL)."}
          </p>
        )}
      </div>
      <Submit>
        Sign in
        <ArrowRight className="size-4" aria-hidden="true" />
      </Submit>
    </form>
  );
}
