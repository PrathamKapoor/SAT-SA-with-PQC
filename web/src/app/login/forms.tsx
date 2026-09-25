"use client";

import { AlertCircle, ArrowRight, FlaskConical, KeyRound, Loader2 } from "lucide-react";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { buttonClass } from "@/components/ui/button";
import { signInWithCredential, startDevelopmentSession, type SignInState } from "@/lib/auth/actions";
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

/** Backend adapter: the production sign-in. */
export function CredentialForm({ next, configured }: { next?: string; configured: boolean }) {
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

export interface IdentityCard {
  principal: string;
  roleLabel: string;
  displayName: string;
  summary: string;
  access: string;
}

function IdentityButton({ card }: { card: IdentityCard }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      name="principal"
      value={card.principal}
      disabled={pending}
      className="group grid w-full grid-cols-[minmax(0,1fr)_auto] items-start gap-3 rounded-md border border-line bg-paper px-4 py-3 text-left transition-colors hover:border-ink/50 hover:bg-canvas focus-visible:border-brand disabled:opacity-60"
    >
      <span className="min-w-0">
        <span className="flex items-baseline gap-2">
          <span className="font-mono text-[12px] font-semibold tracking-[0.08em] text-ink uppercase">{card.roleLabel}</span>
          <span className="font-mono text-[12px] text-brand-strong">{card.principal}</span>
        </span>
        <span className="mt-1 block text-[13px] text-ink-2">{card.summary}</span>
        <span className="mt-1 block text-[11.5px] leading-snug text-muted">
          <span className="sr-only">Access: </span>
          {card.access}
        </span>
      </span>
      <ArrowRight className="mt-1 size-4 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-ink" aria-hidden="true" />
    </button>
  );
}

/** Development adapter: frontend-only identities for previewing each role. */
export function DevelopmentIdentities({ cards, next }: { cards: IdentityCard[]; next?: string }) {
  return (
    <section aria-labelledby="dev-h" className="mt-5">
      <div className="rounded-md border border-attention/30 bg-attention-tint/60 px-4 py-3">
        <h2 id="dev-h" className="flex items-center gap-2 font-mono text-[11.5px] font-semibold tracking-[0.08em] text-attention-strong uppercase">
          <FlaskConical className="size-3.5" aria-hidden="true" />
          Development session
        </h2>
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">
          Backend authentication is not connected in this local development environment. Select a development identity to preview the application.
        </p>
      </div>
      <form action={startDevelopmentSession} className="mt-5">
        <input type="hidden" name="next" value={next ?? ""} />
        <p className="label mb-2">Choose a development identity</p>
        <ul className="space-y-2">
          {cards.map((c) => (
            <li key={c.principal}>
              <IdentityButton card={c} />
            </li>
          ))}
        </ul>
      </form>
      <p className="mt-5 text-[11.5px] leading-relaxed text-muted">
        Development principals exist only in this frontend. They are not backend accounts, carry no credential, and nothing is verified. The session ends when you exit it or close
        the browser.
      </p>
    </section>
  );
}
