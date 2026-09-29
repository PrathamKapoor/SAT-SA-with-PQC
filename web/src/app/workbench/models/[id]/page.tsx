import type { Metadata } from "next";
import Link from "next/link";
import { ReasonAction } from "@/components/domain/model-controls";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { KeyValue, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { api } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { load } from "@/lib/api/guard";
import type { MLModel } from "@/lib/api/types";
import { can } from "@/lib/auth/permissions";
import { fmtDateTime, fmtNum, shortDigest } from "@/lib/domain/format";
import { MODEL_STATE_TONE } from "@/lib/domain/models";

export const metadata: Metadata = { title: "Model" };

const num = (v: number | null | undefined, digits = 3) => (typeof v === "number" ? fmtNum(v, digits) : "Unavailable");

export default async function ModelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ctx = await requireContext();
  const loaded = await load(() => api.mlModel(id));
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <p className="mb-2 text-[12.5px]">
        <Link href="/workbench/models" className="text-muted hover:text-ink">
          Models
        </Link>
      </p>
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Model" />
      ) : (
        <ModelDetail model={loaded.data} canApprove={can(ctx.role, "model.approve")} canDeploy={can(ctx.role, "model.deploy")} />
      )}
    </div>
  );
}

function ModelDetail({ model, canApprove, canDeploy }: { model: MLModel; canApprove: boolean; canDeploy: boolean }) {
  const p = model.passport;
  const e = p.evaluation;
  return (
    <>
      <PageHeader
        eyebrow="Model passport"
        title={`${model.name} v${model.version}`}
        description={p.intended_use}
      />
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <Tag tone={MODEL_STATE_TONE[model.state]}>{model.state}</Tag>
        {model.deployed ? <Tag tone="brand">deployed</Tag> : <Tag>not deployed</Tag>}
        <Tag tone={p.dataset.data_origin === "organizational" ? "neutral" : "attention"}>training data: {p.dataset.data_origin}</Tag>
      </div>

      <Panel className="mb-6" aria-label="Lineage">
        <SectionHeader title="Lineage" />
        <ol className="grid gap-3 text-[12.5px] md:grid-cols-6">
          <li>
            <p className="label">Dataset</p>
            <p className="text-ink">
              {p.dataset.name} v{p.dataset.version}
            </p>
            <p className="mono-id">{shortDigest(p.dataset.content_digest, 16)}</p>
          </li>
          <li>
            <p className="label">Features</p>
            <p className="text-ink">{p.feature_version}</p>
          </li>
          <li>
            <p className="label">Training run</p>
            <p className="mono-id">{p.training_run_id}</p>
            <p className="text-muted">seed {p.random_seed}</p>
          </li>
          <li>
            <p className="label">Evaluation</p>
            <p className="text-ink">{p.verification.passed ? "Meets policy" : "Below policy"}</p>
            <p className="text-muted">{p.verification.policy}</p>
          </li>
          <li>
            <p className="label">Approval</p>
            <p className="text-ink">{model.approval ? fmtDateTime(model.approval.approved_at) : "Not approved"}</p>
            {model.approval && <p className="text-muted">{model.approval.justification}</p>}
          </li>
          <li>
            <p className="label">Deployment</p>
            <p className="text-ink">{model.deployments.length ? `${model.deployments.length} record(s)` : "Never deployed"}</p>
          </li>
        </ol>
      </Panel>

      <div className="mb-6 grid gap-6 md:grid-cols-2">
        <Panel aria-label="Evaluation">
          <SectionHeader title="Holdout evaluation" />
          {e.supervised_metrics !== "available" ? (
            <p className="text-[13px] text-muted">Supervised evaluation unavailable: {e.reason}</p>
          ) : (
            <>
              <KeyValue
                items={[
                  ["ROC-AUC", num(e.roc_auc)],
                  ["PR-AUC", num(e.pr_auc)],
                  ["Brier score", num(e.brier)],
                  ["Precision at 0.5", num(e.precision)],
                  ["Recall at 0.5", num(e.recall)],
                  ["F1 at 0.5", num(e.f1)],
                  ["Holdout runs", e.holdout_rows],
                  ["Training runs", e.training_rows ?? "Not recorded"],
                ]}
              />
              {e.confusion_matrix && (
                <p className="mt-3 text-[12.5px] text-muted">
                  Confusion at 0.5: TP {e.confusion_matrix.tp} · FP {e.confusion_matrix.fp} · FN {e.confusion_matrix.fn} · TN {e.confusion_matrix.tn}
                </p>
              )}
              {e.calibration && e.calibration.length > 0 && (
                <table className="mt-3 w-full text-left text-[12.5px]">
                  <caption className="label mb-1 text-left">Calibration (holdout)</caption>
                  <thead>
                    <tr className="text-muted">
                      <th className="font-normal">Predicted range</th>
                      <th className="font-normal">Runs</th>
                      <th className="font-normal">Mean predicted</th>
                      <th className="font-normal">Observed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {e.calibration.map((b) => (
                      <tr key={b.range[0]} className="text-ink">
                        <td>
                          {b.range[0]}–{b.range[1]}
                        </td>
                        <td>{b.count}</td>
                        <td>{fmtNum(b.mean_predicted, 2)}</td>
                        <td>{fmtNum(b.observed_rate, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
          <p className="mt-3 text-[12.5px] text-muted">{p.verification.reason}</p>
        </Panel>

        <Panel aria-label="Identity">
          <SectionHeader title="Identity" />
          <KeyValue
            columns={1}
            items={[
              ["Algorithm", p.algorithm],
              ["Hyperparameters", JSON.stringify(p.hyperparameters)],
              ["Artifact (SHA3-256)", <span key="a" className="mono-id break-all">{p.artifact.sha3_256}</span>],
              ["Artifact format", p.artifact.format],
              ["Passport digest", <span key="p" className="mono-id break-all">{model.passport_digest}</span>],
              ["Training population", p.training_population],
              ["Environment", Object.entries(p.environment).map(([k, v]) => `${k} ${v}`).join(" · ")],
              ["Registered", fmtDateTime(model.created_at)],
            ]}
          />
        </Panel>
      </div>

      <div className="mb-6 grid gap-6 md:grid-cols-2">
        <Panel aria-label="Features">
          <SectionHeader title="Feature dependencies" />
          <ul className="space-y-1 text-[12.5px]">
            {p.feature_dependencies.map((f) => (
              <li key={f.name}>
                <span className="mono-id">{f.name}</span> <span className="text-muted">{f.definition}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel aria-label="Limitations">
          <SectionHeader title="Known limitations" />
          <ul className="list-disc space-y-1 pl-5 text-[12.5px] text-ink">
            {p.known_limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel className="mb-6" aria-label="History">
        <SectionHeader title="Lifecycle history" />
        <ol className="space-y-1 text-[12.5px]">
          {model.events.map((ev) => (
            <li key={`${ev.to_state}-${ev.created_at}`} className="flex flex-wrap gap-x-3">
              <span className="text-muted">{fmtDateTime(ev.created_at)}</span>
              <span className="text-ink">
                {ev.from_state ?? "new"} → {ev.to_state}
              </span>
              <span className="text-muted">{ev.reason}</span>
            </li>
          ))}
          {model.deployments.map((d) => (
            <li key={d.id} className="flex flex-wrap gap-x-3">
              <span className="text-muted">{fmtDateTime(d.created_at)}</span>
              <span className="text-ink">{d.kind}</span>
              <span className="text-muted">{d.active ? "active" : `inactive since ${fmtDateTime(d.deactivated_at)}`}</span>
            </li>
          ))}
        </ol>
      </Panel>

      {(canApprove || canDeploy) && (
        <Panel aria-label="Governance">
          <SectionHeader title="Governance" />
          <div className="grid gap-6 md:grid-cols-3">
            {canApprove && model.state === "verified" && <ReasonAction kind="approve" id={model.id} />}
            {canDeploy && model.state === "approved" && !model.deployed && <ReasonAction kind="deploy" id={model.id} />}
            {canApprove && !model.deployed && model.state !== "retired" && <ReasonAction kind="retire" id={model.id} />}
          </div>
          <p className="mt-3 text-[12.5px] text-muted">
            The user who requested training cannot approve its model. Only an approved model whose artifact verifies against its digest can be deployed.
          </p>
        </Panel>
      )}
    </>
  );
}
