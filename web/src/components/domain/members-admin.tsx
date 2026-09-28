"use client";

import { Loader2, UserMinus, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { ActionError } from "@/components/ui/api-state";
import { Button } from "@/components/ui/button";
import type { ApiErrorInfo } from "@/lib/api/errors";
import type { Invitation, MembershipRole } from "@/lib/api/types";
import { ROLE_LABEL, ROLE_SUMMARY, ROLES_IN_ORDER } from "@/lib/auth/permissions";
import { inviteMemberAction, revokeMemberAction } from "@/lib/workbench/actions";

const input =
  "h-9 w-full rounded-sm border border-line-2 bg-paper px-3 text-[13.5px] text-ink focus:border-brand focus:ring-2 focus:ring-brand/20 focus:outline-none";

/** POST /api/v1/members: the new member's credential is shown here once and never stored. */
export function InviteMember() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MembershipRole>("satsa_viewer");
  const [issued, setIssued] = useState<Invitation | null>(null);
  const [error, setError] = useState<ApiErrorInfo | null>(null);
  const [pending, start] = useTransition();

  return (
    <div>
      <form
        className="grid gap-3 md:grid-cols-[1fr_1fr_12rem_auto] md:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          start(async () => {
            setError(null);
            setIssued(null);
            const r = await inviteMemberAction({ name: name.trim(), email: email.trim(), role });
            if (!r.ok) setError(r.error);
            else {
              setIssued(r.data);
              setName("");
              setEmail("");
              router.refresh();
            }
          });
        }}
      >
        <label className="block">
          <span className="label mb-1 block">Name</span>
          <input className={input} value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
        </label>
        <label className="block">
          <span className="label mb-1 block">Email</span>
          <input className={input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={320} />
        </label>
        <label className="block">
          <span className="label mb-1 block">Role</span>
          <select className={input} value={role} onChange={(e) => setRole(e.target.value as MembershipRole)}>
            {ROLES_IN_ORDER.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" variant="primary" disabled={pending || !name.trim() || !email.trim()}>
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <UserPlus className="size-4" aria-hidden="true" />}
          Add member
        </Button>
      </form>
      <p className="mt-2 text-[12px] text-muted">{ROLE_SUMMARY[role]}</p>
      <ActionError error={error} />
      {issued && (
        <div role="status" className="mt-4 rounded-md border border-attention/40 bg-attention-tint/60 px-4 py-3">
          <p className="text-[13.5px] font-medium text-ink">
            {issued.name} was added as {ROLE_LABEL[issued.role]}. Give them this credential now: it is shown once and cannot be retrieved later.
          </p>
          <p className="mt-2 font-mono text-[12.5px] break-all text-ink select-all" data-issued-credential>
            {issued.credential}
          </p>
        </div>
      )}
    </div>
  );
}

/** DELETE /api/v1/members/{user_id}: revokes the membership. */
export function RevokeMember({ userId, name }: { userId: string; name: string }) {
  const router = useRouter();
  const [error, setError] = useState<ApiErrorInfo | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [pending, start] = useTransition();
  return (
    <div className="text-right">
      {confirming ? (
        <span className="inline-flex items-center gap-2">
          <span className="text-[12px] text-muted">Revoke {name}?</span>
          <Button
            size="sm"
            variant="attention"
            disabled={pending}
            onClick={() =>
              start(async () => {
                const r = await revokeMemberAction(userId);
                if (!r.ok) setError(r.error);
                else router.refresh();
                setConfirming(false);
              })
            }
          >
            Revoke
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
            Keep
          </Button>
        </span>
      ) : (
        <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}>
          <UserMinus className="size-3.5" aria-hidden="true" />
          Revoke
        </Button>
      )}
      <ActionError error={error} />
    </div>
  );
}
