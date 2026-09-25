import type { Metadata } from "next";
import { toRowData } from "@/components/domain/finding-row";
import { ReviewQueue, type QueueItem } from "@/components/domain/review-queue";
import { PageHeader } from "@/components/ui/layout";
import { getSource } from "@/lib/api";
import { can, ROLE_LABEL } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";
import { byPriority, loadFindingViews } from "@/lib/model";

export const metadata: Metadata = { title: "Review queue" };

export default async function ReviewQueuePage() {
  const session = (await getSession())!;
  const [findings, decisions] = await Promise.all([loadFindingViews(), getSource().listReviewDecisions()]);
  const items: QueueItem[] = findings
    .filter((f) => f.state === "signal")
    .sort(byPriority)
    .map((f) => ({
      ...toRowData(f),
      contentDigest: f.contentDigest,
      limitations: f.limitations,
      history: decisions.filter((d) => d.findingId === f.id).sort((a, b) => a.occurredAt - b.occurredAt),
    }));

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Supervision"
        title="Review queue"
        description="Findings waiting for a supervisory decision, most important first. Each decision is bound to the finding's content digest at the moment it is recorded."
      />
      <ReviewQueue items={items} canRecord={can(session.user.role, "decision.record")} roleLabel={ROLE_LABEL[session.user.role]} sessionMode={session.mode} />
    </div>
  );
}
