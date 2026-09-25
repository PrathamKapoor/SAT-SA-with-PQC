import type { Metadata } from "next";
import { KeyRound, Lock, ShieldCheck, WifiOff } from "lucide-react";

export const metadata: Metadata = {
  title: "Security and trust",
  description: "How SAT-SA protects evidence integrity, access and the supervisory decision record.",
};

const PILLARS = [
  {
    icon: ShieldCheck,
    title: "Verifiable evidence",
    points: [
      "Every analysis run and finding is signed with ML-DSA-65 over a SHA3-256 digest of its canonical form.",
      "Verification rebuilds the digest from the stored record, so any edited column, including the stored digest, is detected.",
      "Provenance links source file, record, observation, finding, risk, recommendation and decision.",
    ],
  },
  {
    icon: KeyRound,
    title: "Accountable decisions",
    points: [
      "Only the supervisor and administrator roles can record a review decision.",
      "Each decision is bound to the finding's content digest at the moment it was made.",
      "Decisions are mirrored into an append-only, hash-chained ledger, so deletion or reordering is detectable.",
    ],
  },
  {
    icon: Lock,
    title: "Controlled access",
    points: [
      "Five roles: viewer, analyst, supervisor, auditor and administrator, each with explicit permissions.",
      "Sign-in uses a credential issued by an administrator; sessions are held in HttpOnly cookies with CSRF protection and rate-limited sign-in.",
      "The backend enforces every permission; the interface only reflects it.",
    ],
  },
  {
    icon: WifiOff,
    title: "Offline by design",
    points: [
      "The analytical pipeline makes no network calls; a test blocks DNS and TCP and runs the full demo.",
      "Installation works from a local wheel bundle with the package index unreachable.",
      "Data stays in a local evidence store on the host.",
    ],
  },
];

export default function SecurityPage() {
  return (
    <div className="mx-auto max-w-[1320px] px-5 pt-16 pb-20 md:px-8">
      <p className="label">Security and trust</p>
      <h1 className="mt-4 max-w-[20ch] text-[40px] leading-[1.04] font-semibold tracking-[-0.035em] text-ink md:text-[60px]">
        A result is only useful if it can be checked.
      </h1>
      <p className="mt-6 max-w-2xl text-[17px] leading-relaxed text-muted">
        TRUST-SAT is the evidence-integrity layer of SAT-SA. It answers one question for every record: has this changed since it was produced?
      </p>

      <ul className="mt-16 grid gap-x-12 gap-y-14 md:grid-cols-2">
        {PILLARS.map((p) => (
          <li key={p.title} className="border-t border-ink pt-6">
            <p.icon className="size-6 text-brand" strokeWidth={1.5} aria-hidden="true" />
            <h2 className="mt-4 text-[22px] font-semibold tracking-[-0.015em] text-ink">{p.title}</h2>
            <ul className="mt-4 space-y-3 text-[15px] leading-relaxed text-ink-2">
              {p.points.map((pt) => (
                <li key={pt} className="border-l border-line-2 pl-4">
                  {pt}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>

      <section aria-labelledby="lim-h" className="mt-20 rounded-md border border-line bg-canvas px-6 py-8 md:px-10">
        <h2 id="lim-h" className="text-[20px] font-semibold text-ink">
          Stated limits
        </h2>
        <ul className="mt-5 grid gap-5 text-[14px] leading-relaxed text-ink-2 md:grid-cols-3">
          <li>Detection of tampering at verification time, not tamper-proof storage. Someone holding both the database and the key could replace both.</li>
          <li>The ML-DSA and ML-KEM implementations are pure Python and not side-channel hardened. Migration to a hardened library is the stated path.</li>
          <li>No PKCS#11 hardware token supports ML-DSA today, so keys are held in a software keystore. The platform fails closed when a token is required.</li>
        </ul>
      </section>
    </div>
  );
}
