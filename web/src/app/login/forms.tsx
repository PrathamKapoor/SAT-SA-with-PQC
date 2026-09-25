"use client";

import { AlertCircle, ArrowRight, FlaskConical, KeyRound, Loader2 } from "lucide-react";
import { useActionState, useState } from "react";
import { useFormStatus } from "react-dom";
import { buttonClass } from "@/components/ui/button";
import { signInWithCredential, startDevelopmentSession, type SignInState } from "@/lib/auth/actions";
import { ROLE_LABEL, ROLE_SUMMARY, ROLES_IN_ORDER } from "@/lib/auth/permissions";
import type { SatsaRole } from "@/lib/types/domain";
import { cn } from "@/lib/utils";

function Submit({ children, variant = "primary" }: { children: React.ReactNode; variant?: "primary" | "secondary" }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending} aria-disabled={pending} className={buttonClass(variant, "lg", "w-full")}>
      {pending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
      {pending ? "Verifying" : children}
    </button>
  );
}

export function CredentialForm({ next }: { next?: string }) {
  const [state, action] = useActionState<SignInState, FormData>(signInWithCredential, { error: null });
  return (
    <form action={action} className="mt-8 space-y-4" noValidate>
      <input type="hidden" name="next" value={next ?? ""} />
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
            Format key_id.secret, as shown once when the credential was issued.
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

/** Fixture mode only. Explicitly not authentication. */
export function DevelopmentSessionForm({ next }: { next?: string }) {
  const [role, setRole] = useState<SatsaRole>("satsa_supervisor");
  return (
    <section aria-labelledby="dev-session" className="mt-8 rounded-md border border-attention/30 bg-attention-tint/60 p-4">
      <div className="flex items-start gap-2.5">
        <FlaskConical className="mt-0.5 size-4 shrink-0 text-attention" aria-hidden="true" />
        <div>
          <h3 id="dev-session" className="text-[13.5px] font-semibold text-ink">
            Development session
          </h3>
          <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">
            Backend authentication is not connected in this environment. Choose a role to explore the interface with the development fixture. Nothing is verified.
          </p>
        </div>
      </div>
      <form action={startDevelopmentSession} className="mt-4">
        <input type="hidden" name="next" value={next ?? ""} />
        <fieldset>
          <legend className="sr-only">Role</legend>
          <div className="grid gap-1">
            {ROLES_IN_ORDER.map((r) => (
              <label
                key={r}
                className={cn(
                  "flex cursor-pointer items-start gap-2.5 rounded-sm border bg-paper px-3 py-1.5 transition-colors",
                  role === r ? "border-ink" : "border-line hover:border-line-2",
                )}
              >
                <input type="radio" name="role" value={r} checked={role === r} onChange={() => setRole(r)} className="mt-1 accent-[#0c1222]" />
                <span>
                  <span className="block text-[13px] font-medium text-ink">{ROLE_LABEL[r]}</span>
                  <span className="block text-[11.5px] leading-snug text-muted">{ROLE_SUMMARY[r]}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="mt-3">
          <Submit variant="secondary">Continue as {ROLE_LABEL[role]}</Submit>
        </div>
      </form>
    </section>
  );
}
