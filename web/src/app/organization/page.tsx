import type { Metadata } from "next";
import { ArrowRight, Building2 } from "lucide-react";
import { Wordmark } from "@/components/brand";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { requireSignedIn } from "@/lib/api/context";
import { selectOrganization, signOut } from "@/lib/auth/actions";
import { ROLE_LABEL } from "@/lib/auth/permissions";

export const metadata: Metadata = { title: "Select organization", robots: { index: false } };

const REASON: Record<string, string> = {
  unavailable: "The previously selected organization is no longer available to you.",
  unreachable: "The SAT-SA service could not confirm the organization. Try again.",
};

export default async function OrganizationPage({ searchParams }: { searchParams: Promise<{ reason?: string }> }) {
  const { reason } = await searchParams;
  const { session, organizations } = await requireSignedIn();
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-canvas px-6 py-10">
      <div className="w-full max-w-[28rem]">
        <Wordmark sub />
        <div className="mt-8 flex items-center gap-2 text-muted">
          <Building2 className="size-4" aria-hidden="true" />
          <p className="label">Organization</p>
        </div>
        <h1 className="mt-3 text-[26px] font-semibold tracking-[-0.02em] text-ink">Choose where to work</h1>
        <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
          Signed in as <span className="font-medium text-ink">{session.name}</span>. Every request is scoped to the organization you choose, and the SAT-SA service checks
          your membership on each one.
        </p>
        {reason && REASON[reason] && <ErrorState className="mt-5" title={REASON[reason]} />}
        {organizations.length === 0 ? (
          <EmptyState className="mt-6" title="No active membership">
            Your identity is not a member of any organization. An organization administrator must add you before you can use the workbench.
          </EmptyState>
        ) : (
          <form action={selectOrganization} className="mt-6">
            <ul className="space-y-2" aria-label="Your organizations">
              {organizations.map((o) => (
                <li key={o.id}>
                  <button
                    type="submit"
                    name="organization"
                    value={o.id}
                    className="group grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md border border-line bg-paper px-4 py-3 text-left transition-colors hover:border-ink/50 hover:bg-canvas focus-visible:border-brand"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-[14px] font-semibold text-ink">{o.name}</span>
                      <span className="mt-0.5 block text-[12.5px] text-muted">
                        {ROLE_LABEL[o.role] ?? o.role} <span className="mono-id">· {o.id}</span>
                      </span>
                    </span>
                    <ArrowRight className="size-4 text-faint group-hover:text-ink" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          </form>
        )}
        <form action={signOut} className="mt-8">
          <button type="submit" className="text-[13px] text-muted underline-offset-4 hover:text-ink hover:underline">
            Sign out
          </button>
        </form>
      </div>
    </main>
  );
}
