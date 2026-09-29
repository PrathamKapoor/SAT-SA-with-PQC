import type { Metadata } from "next";
import Link from "next/link";
import {
  AcceptRetrainingForm,
  CreateDatasetButton,
  DatasetJobButton,
  DriftCheckButton,
  ReasonAction,
} from "@/components/domain/model-controls";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { Metric, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { load } from "@/lib/api/guard";
import type { MLDriftReport, MLModel } from "@/lib/api/types";
import { can } from "@/lib/auth/permissions";
import { fmtDateTime, fmtNum, shortDigest } from "@/lib/domain/format";
import { DATASET_TONE, DRIFT_LABEL, DRIFT_TONE, MODEL_STATE_TONE } from "@/lib/domain/models";

export const metadata: Metadata = { title: "Models" };

function metric(model: MLModel, key: "roc_auc" | "brier") {
  const value = model.passport.evaluation[key];
  return typeof value === "number" ? fmtNum(value, 3) : "Unavailable";
}

export default async function ModelsPage() {
  const ctx = await requireContext();
  const loaded = await load(async () => {
    const [models, datasets, monitoring, drift, requests, deployments] = await Promise.all([
      api.mlModels({ limit: 50 }),
      api.mlDatasets({ limit: 20 }),
      api.mlMonitoring(),
      api.mlDriftReports({ limit: 10 }),
      api.mlRetrainingRequests({ limit: 20 }),
      api.mlDeployments({ limit: 20 }),
    ]);
    return { models: models.items, datasets: datasets.items, monitoring, drift: drift.items, requests: requests.items, deployments: deployments.items };
  });
  const canTrain = can(ctx.role, "model.train");
  const canGovern = can(ctx.role, "model.approve");

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Analytics"
        title="Review-outcome model"
        description="An advisory model trained on this organization's own supervisory decisions. It estimates how likely a supervisor is to confirm or escalate a run, to help order the review queue. It never changes findings or decisions, and it abstains when it cannot score reliably."
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Models" />
      ) : (
        <ModelsBody data={loaded.data} canTrain={canTrain} canGovern={canGovern} />
      )}
    </div>
  );
}

function ModelsBody({
  data,
  canTrain,
  canGovern,
}: {
  data: {
    models: MLModel[];
    datasets: Awaited<ReturnType<typeof api.mlDatasets>>["items"];
    monitoring: Awaited<ReturnType<typeof api.mlMonitoring>>;
    drift: MLDriftReport[];
    requests: Awaited<ReturnType<typeof api.mlRetrainingRequests>>["items"];
    deployments: Awaited<ReturnType<typeof api.mlDeployments>>["items"];
  };
  canTrain: boolean;
  canGovern: boolean;
}) {
  const { models, datasets, monitoring, drift, requests, deployments } = data;
  const active = models.find((m) => m.deployed) ?? null;
  const observed = monitoring.active_model;
  const validDatasets = datasets.filter((d) => d.status === "valid");
  return (
    <>
      <dl className="mb-6 grid grid-cols-2 gap-6 md:grid-cols-4">
        <Metric label="Deployed model" value={active ? `v${active.version}` : "None"} tone={active ? "brand" : "ink"} />
        <Metric label="Inferences (active model)" value={observed ? observed.inferences : 0} />
        <Metric label="Abstained" value={observed ? observed.abstained : 0} tone={observed?.abstained ? "attention" : "ink"} />
        <Metric
          label="Realized ROC-AUC"
          value={observed?.realized_performance.status === "available" ? fmtNum(observed.realized_performance.roc_auc, 3) : "Insufficient labels"}
        />
      </dl>

      <Panel className="mb-6" aria-label="Deployment">
        <SectionHeader title="Deployment" />
        {monitoring.status === "no_deployed_model" ? (
          <EmptyState title="No model is deployed">Runs record an explicit abstention (no deployed model) and review proceeds without a score.</EmptyState>
        ) : (
          <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_20rem]">
            <div>
              {active && (
                <p className="text-[14px] text-ink">
                  <Link href={`/workbench/models/${active.id}`} className="font-semibold hover:text-brand-strong">
                    {active.name} v{active.version}
                  </Link>{" "}
                  <span className="mono-id">{shortDigest(active.artifact_digest, 16)}</span>
                </p>
              )}
              {monitoring.status === "no_observations" ? (
                <p className="mt-2 text-[13px] text-muted">No inferences recorded yet for this model.</p>
              ) : (
                observed && (
                  <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-[12.5px] md:grid-cols-4">
                    <dt className="text-muted">Scored</dt>
                    <dd className="text-ink">{observed.scored}</dd>
                    <dt className="text-muted">Missing features</dt>
                    <dd className="text-ink">{fmtNum(observed.missing_feature_rate * 100, 1)}%</dd>
                    <dt className="text-muted">Score median</dt>
                    <dd className="text-ink">{observed.score_distribution ? fmtNum(observed.score_distribution.p50, 3) : "No scores"}</dd>
                    <dt className="text-muted">Latency p95</dt>
                    <dd className="text-ink">{fmtNum(observed.latency_ms.p95, 2)} ms</dd>
                  </dl>
                )
              )}
              {Object.keys(monitoring.all_models.abstentions_by_reason).length > 0 && (
                <p className="mt-3 text-[12.5px] text-muted">
                  Abstentions (all models):{" "}
                  {Object.entries(monitoring.all_models.abstentions_by_reason)
                    .map(([reason, n]) => `${reason.replaceAll("_", " ")} ${n}`)
                    .join(" · ")}
                </p>
              )}
            </div>
            {canGovern && <ReasonAction kind="rollback" />}
          </div>
        )}
        {deployments.length > 0 && (
          <ol className="mt-4 space-y-1 text-[12.5px]" aria-label="Deployment history">
            {deployments.map((d) => (
              <li key={d.id} className="flex flex-wrap gap-x-3">
                <span className="text-muted">{fmtDateTime(d.created_at)}</span>
                <Tag tone={d.active ? "brand" : "neutral"}>{d.active ? "active" : "inactive"}</Tag>
                <span className="text-ink">{d.kind}</span>
                <span className="mono-id">{d.model_id}</span>
                {d.reason && <span className="text-muted">{d.reason}</span>}
              </li>
            ))}
          </ol>
        )}
      </Panel>

      <Panel className="mb-6" aria-label="Model versions">
        <SectionHeader title="Model versions" />
        {models.length === 0 ? (
          <EmptyState title="No model has been trained">Build a dataset from recorded decisions, validate it, then train.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {models.map((m) => (
              <li key={m.id} className="grid gap-3 rounded-md border border-line bg-paper px-4 py-3 md:grid-cols-[10rem_minmax(0,1fr)_14rem]">
                <div>
                  <Link href={`/workbench/models/${m.id}`} className="text-[14px] font-semibold text-ink hover:text-brand-strong">
                    v{m.version}
                  </Link>{" "}
                  <Tag tone={MODEL_STATE_TONE[m.state]}>{m.state}</Tag> {m.deployed && <Tag tone="brand">deployed</Tag>}
                </div>
                <dl className="grid grid-cols-2 gap-x-4 text-[12.5px] md:grid-cols-4">
                  <dt className="text-muted">Holdout ROC-AUC</dt>
                  <dd className="text-ink">{metric(m, "roc_auc")}</dd>
                  <dt className="text-muted">Brier</dt>
                  <dd className="text-ink">{metric(m, "brier")}</dd>
                  <dt className="text-muted">Training data</dt>
                  <dd className="text-ink">
                    {m.passport.dataset.record_count} runs <Tag tone={m.passport.dataset.data_origin === "organizational" ? "neutral" : "attention"}>{m.passport.dataset.data_origin}</Tag>
                  </dd>
                  <dt className="text-muted">Registered</dt>
                  <dd className="text-ink">{fmtDateTime(m.created_at)}</dd>
                </dl>
                <p className="text-[12.5px] text-muted">{m.passport.verification.reason}</p>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel className="mb-6" aria-label="Datasets">
        <SectionHeader title="Datasets" />
        {canTrain && (
          <div className="mb-4">
            <CreateDatasetButton />
          </div>
        )}
        {datasets.length === 0 ? (
          <EmptyState title="No dataset versions">A dataset is a snapshot of recorded supervisory decisions and the features of the decided runs.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {datasets.map((d) => (
              <li key={d.id} className="grid gap-3 rounded-md border border-line bg-paper px-4 py-3 md:grid-cols-[minmax(0,1fr)_16rem]">
                <div>
                  <p className="text-[13.5px] text-ink">
                    <span className="font-semibold">
                      {d.name} v{d.version}
                    </span>{" "}
                    <Tag tone={DATASET_TONE[d.status]}>{d.status}</Tag> <Tag tone={d.data_origin === "organizational" ? "neutral" : "attention"}>{d.data_origin}</Tag>
                  </p>
                  <p className="mt-1 text-[12.5px] text-muted">
                    {d.record_count} runs · confirmed/escalated {d.label_counts["1"] ?? 0} · dismissed {d.label_counts["0"] ?? 0} ·{" "}
                    <span className="mono-id">{shortDigest(d.content_digest, 16)}</span>
                  </p>
                  {d.validation && (
                    <ul className="mt-2 grid gap-x-4 text-[12px] md:grid-cols-2">
                      {d.validation.checks.map((c) => (
                        <li key={c.check} className={c.passed ? "text-muted" : "text-critical"}>
                          {c.passed ? "Pass" : "Fail"} · {c.check.replaceAll("_", " ")}: {c.detail}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                {canTrain && (
                  <div className="flex flex-col gap-2">
                    {d.status === "created" && <DatasetJobButton datasetId={d.id} kind="validate" />}
                    {d.status === "valid" && <DatasetJobButton datasetId={d.id} kind="train" />}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <div className="grid gap-6 md:grid-cols-2">
        <Panel aria-label="Drift">
          <SectionHeader title="Drift" />
          <p className="mb-3 text-[12.5px] text-muted">
            Population stability index of recent scores against the training population. Fewer than the policy minimum of observations reports insufficient
            data, never &ldquo;no drift&rdquo;.
          </p>
          {canTrain && active && (
            <div className="mb-3">
              <DriftCheckButton />
            </div>
          )}
          {drift.length === 0 ? (
            <EmptyState title="No drift checks yet">Checks run as worker jobs against the deployed model.</EmptyState>
          ) : (
            <ul className="space-y-2 text-[12.5px]">
              {drift.map((r) => (
                <li key={r.id} className="rounded-md border border-line bg-paper px-3 py-2">
                  <Tag tone={DRIFT_TONE[r.result]}>{DRIFT_LABEL[r.result]}</Tag>{" "}
                  <span className="text-ink">
                    PSI {typeof r.details.score_psi === "number" ? fmtNum(r.details.score_psi, 3) : "n/a"} (threshold {fmtNum(r.threshold, 2)})
                  </span>
                  <p className="text-muted">
                    baseline {r.baseline_count} · current {r.current_count} · {fmtDateTime(r.created_at)}
                  </p>
                  {r.details.reason && <p className="text-muted">{r.details.reason}</p>}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel aria-label="Retraining">
          <SectionHeader title="Retraining" />
          <p className="mb-3 text-[12.5px] text-muted">
            Sustained drift or degraded realized performance opens a request. Nothing retrains or deploys on its own: a supervisor accepts a request, and the
            resulting model still needs approval and deployment.
          </p>
          {canTrain && (
            <div className="mb-3">
              <ReasonAction kind="request" />
            </div>
          )}
          {requests.length === 0 ? (
            <EmptyState title="No retraining requests">Requests appear here with the evidence that triggered them.</EmptyState>
          ) : (
            <ul className="space-y-3">
              {requests.map((r) => (
                <li key={r.id} className="rounded-md border border-line bg-paper px-3 py-2 text-[12.5px]">
                  <p>
                    <Tag tone={r.status === "open" ? "attention" : "neutral"}>{r.status}</Tag> <span className="text-ink">{r.trigger}</span>{" "}
                    <span className="text-muted">{fmtDateTime(r.created_at)}</span>
                  </p>
                  {r.resolution && <p className="text-muted">{r.resolution}</p>}
                  {canGovern && r.status === "open" && (
                    <div className="mt-2 grid gap-3 md:grid-cols-2">
                      <AcceptRetrainingForm requestId={r.id} datasets={validDatasets} />
                      <ReasonAction kind="dismiss" id={r.id} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}
