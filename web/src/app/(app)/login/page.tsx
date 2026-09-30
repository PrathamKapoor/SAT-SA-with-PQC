import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ArrowLeft, Lock } from "lucide-react";
import { Wordmark } from "@/components/brand";
import { LoginVisual } from "@/components/public/evidence-field/LoginVisual";
import { apiBase, SESSION_COOKIE } from "@/lib/api/client";
import { CredentialForm } from "./forms";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

const NOTICE: Record<string, string> = {
  expired: "Your session ended. Sign in again to continue.",
  "signed-out": "You are signed out.",
};

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ reason?: string }> }) {
  // A present session cookie is resolved by the workbench, which returns here if it is invalid.
  if ((await cookies()).get(SESSION_COOKIE)) redirect("/workbench");
  const { reason } = await searchParams;

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
          <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
            Use the credential issued to your identity by a SAT-SA administrator. Access is limited to your role in each organization.
          </p>
          {reason && NOTICE[reason] && (
            <p role="status" className="mt-4 rounded-md border border-line bg-canvas px-3 py-2 text-[13px] text-ink-2">
              {NOTICE[reason]}
            </p>
          )}
          <CredentialForm configured={Boolean(apiBase())} />
          <p className="mt-10 text-[12px] leading-relaxed text-faint">
            The credential is sent once to the SAT-SA service, which returns a revocable session. Only that session is kept, in an HttpOnly cookie; the credential is not
            stored.
          </p>
        </div>
      </main>
    </div>
  );
}
