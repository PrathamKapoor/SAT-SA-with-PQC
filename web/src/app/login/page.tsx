import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft, FileCheck2, Lock, ShieldCheck, UserCheck } from "lucide-react";
import { Wordmark } from "@/components/brand";
import { getSession, sessionMode } from "@/lib/auth/session";
import { CredentialForm, DevelopmentSessionForm } from "./forms";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  if (await getSession()) redirect("/workbench");
  const { next } = await searchParams;
  const mode = sessionMode();

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,34rem)]">
      <section aria-label="About this system" className="relative hidden overflow-hidden border-r border-line bg-canvas lg:sticky lg:top-0 lg:flex lg:h-dvh lg:flex-col">
        <div className="flex items-center justify-between px-10 pt-9">
          <Wordmark sub />
          <Link href="/" className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
            <ArrowLeft className="size-3.5" aria-hidden="true" />
            Public site
          </Link>
        </div>

        <div className="mt-auto px-10 pb-12">
          <p className="label">Supervisory Analytics Tool for SOC Assessment</p>
          <h1 className="mt-4 max-w-[15ch] text-[44px] leading-[1.02] font-semibold tracking-[-0.035em] text-ink xl:text-[56px]">
            Evidence first. Human decision last.
          </h1>
          <ul className="mt-8 grid max-w-2xl grid-cols-3 gap-5 text-[13px] leading-snug text-ink-2">
            <li className="border-t border-line-2 pt-3">
              <FileCheck2 className="mb-2 size-4 text-brand" aria-hidden="true" />
              Periodic CSE submissions analysed offline. No live telemetry.
            </li>
            <li className="border-t border-line-2 pt-3">
              <UserCheck className="mb-2 size-4 text-brand" aria-hidden="true" />
              Findings are recommendations. Supervisors hold the decision.
            </li>
            <li className="border-t border-line-2 pt-3">
              <ShieldCheck className="mb-2 size-4 text-brand" aria-hidden="true" />
              Every run and finding signed with ML-DSA-65 over SHA3-256.
            </li>
          </ul>
        </div>
        <svg aria-hidden="true" className="pointer-events-none absolute top-24 right-0 h-[46%] w-[70%] text-line-2" viewBox="0 0 400 260" fill="none">
          {Array.from({ length: 7 }).map((_, i) => (
            <path key={i} d={`M0 ${40 + i * 30} C 120 ${20 + i * 30}, 220 ${90 + i * 18}, 400 ${120 + i * 4}`} stroke="currentColor" strokeWidth="1" />
          ))}
          <rect x="330" y="104" width="30" height="30" rx="3" className="fill-brand/80" />
        </svg>
      </section>

      <main className="flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-10 lg:hidden">
            <Wordmark sub />
          </div>
          <div className="flex items-center gap-2 text-muted">
            <Lock className="size-4" aria-hidden="true" />
            <p className="label">Secure sign in</p>
          </div>
          <h2 className="mt-3 text-[26px] font-semibold tracking-[-0.02em] text-ink">Sign in to SAT-SA</h2>
          <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
            Use the credential issued to your identity by a SAT-SA administrator. Access is limited to your assigned role.
          </p>

          <CredentialForm next={next} />

          {mode === "development" && <DevelopmentSessionForm next={next} />}

          <p className="mt-10 text-[12px] leading-relaxed text-faint">
            Sessions use an HttpOnly cookie. Credentials are verified by the SAT-SA service, never in the browser.
          </p>
        </div>
      </main>
    </div>
  );
}
