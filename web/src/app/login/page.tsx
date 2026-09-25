import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft, Lock } from "lucide-react";
import { Wordmark } from "@/components/brand";
import { LoginVisual } from "@/components/public/evidence-field/LoginVisual";
import { backendAuthConfigured } from "@/lib/auth/config";
import { DEV_IDENTITIES } from "@/lib/auth/identities";
import { can, ROLE_LABEL } from "@/lib/auth/permissions";
import { getSession, sessionMode } from "@/lib/auth/session";
import { NAV } from "@/lib/nav";
import type { SatsaRole } from "@/lib/types/domain";
import { CredentialForm, DevelopmentIdentities, type IdentityCard } from "./forms";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

export default async function LoginPage() {
  if (await getSession()) redirect("/workbench");
  const mode = sessionMode();

  // Areas each role opens beyond the read-only set every role shares (existing permissions only).
  const areasFor = (role: SatsaRole) => NAV.flatMap((g) => g.items).filter((i) => !i.requires || can(role, i.requires)).map((i) => i.label);
  const shared = new Set(areasFor("satsa_viewer"));
  const cards: IdentityCard[] = DEV_IDENTITIES.map((d) => {
    const extra = areasFor(d.role).filter((a) => !shared.has(a));
    const decides = can(d.role, "decision.record");
    return {
      principal: d.principal,
      roleLabel: ROLE_LABEL[d.role],
      displayName: d.displayName,
      summary: d.summary,
      access: [extra.length ? `Read-only areas, plus ${extra.join(", ")}` : "Read-only areas only", decides ? "records review decisions" : "cannot record decisions"].join(" · "),
    };
  });

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,36rem)]">
      <section aria-label="About this system" className="relative hidden overflow-hidden border-r border-line bg-paper lg:sticky lg:top-0 lg:flex lg:h-dvh lg:flex-col">
        <div className="relative z-10 flex items-center justify-between px-10 pt-9">
          <Wordmark sub />
          <Link href="/" className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
            <ArrowLeft className="size-3.5" aria-hidden="true" />
            Public site
          </Link>
        </div>
        <LoginVisual />
        <div className="pointer-events-none relative z-10 mt-auto px-10 pb-10">
          <p className="label">Supervisory Analytics for SOC Assessment</p>
          <p className="mt-3 max-w-[20ch] text-[36px] leading-[1.04] font-semibold tracking-[-0.03em] text-ink xl:text-[44px]">Evidence first. Human decision last.</p>
        </div>
      </section>

      <main className="flex flex-col justify-center px-6 py-10 sm:px-12">
        <div className="mx-auto w-full max-w-[26rem]">
          <div className="mb-8 lg:hidden">
            <Wordmark sub />
          </div>
          <div className="flex items-center gap-2 text-muted">
            <Lock className="size-4" aria-hidden="true" />
            <p className="label">Sign in</p>
          </div>
          <h1 className="mt-3 text-[26px] font-semibold tracking-[-0.02em] text-ink">Sign in to SAT-SA</h1>

          {mode === "development" ? (
            <DevelopmentIdentities cards={cards} />
          ) : (
            <>
              <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
                Use the credential issued to your identity by a SAT-SA administrator. Access is limited to your assigned role.
              </p>
              <CredentialForm configured={backendAuthConfigured()} />
              <p className="mt-10 text-[12px] leading-relaxed text-faint">
                Sessions use an HttpOnly cookie. Credentials are verified by the SAT-SA service, never in the browser.
              </p>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
