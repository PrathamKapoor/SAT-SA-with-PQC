"""Command-line interface for the Quantum-Secure Agentic MLOps platform."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from qsmlops.config import PlatformConfig
from qsmlops.pipeline.selfheal import SelfHealingMLOps


@click.group()
@click.option(
    "--home",
    envvar="QSMLOPS_HOME",
    default=None,
    help="Platform root directory (default: ~/.qsmlops)",
)
@click.pass_context
def cli(ctx, home):
    """qsmlops: Quantum-Secure Agentic MLOps Pipeline Management System."""
    ctx.ensure_object(dict)
    config = PlatformConfig(Path(home) if home else None)
    ctx.obj["config"] = config
    ctx.obj["pipeline"] = SelfHealingMLOps(config)


def _dump(obj):
    click.echo(json.dumps(obj, indent=2, sort_keys=True, default=str))


@cli.command()
@click.pass_context
def init(ctx):
    """Initialize platform directories and bootstrap trust anchors."""
    pipeline = ctx.obj["pipeline"]
    pipeline.config.ensure_dirs()
    _dump({"status": "initialized", "root": str(pipeline.config.root)})


@cli.command()
@click.option("--name", required=True, help="Dataset name")
@click.option("--samples", default=200, help="Synthetic sample count")
@click.option("--seed", default=42, help="RNG seed for reproducibility")
@click.pass_context
def provision_dataset(ctx, name, samples, seed):
    """Create and provision a synthetic regression dataset."""
    pipeline = ctx.obj["pipeline"]
    from qsmlops.pipeline.training import make_synthetic_regression

    ds = make_synthetic_regression(n=samples, seed=seed)
    result = pipeline.provision_dataset(name, ds)
    _dump(result)


@cli.command()
@click.option("--model", "model_name", required=True)
@click.option("--dataset", "dataset_name", required=True)
@click.option("--version", type=int, default=None)
@click.pass_context
def train(ctx, model_name, dataset_name, version):
    """Train a model, build BOM, sign passport, register in registry."""
    pipeline = ctx.obj["pipeline"]
    result = pipeline.train_and_register(model_name, dataset_name, version)
    _dump(result)


@cli.command()
@click.option("--version-id", required=True)
@click.pass_context
def verify(ctx, version_id):
    """Run agent evaluation and registry verification for a version."""
    pipeline = ctx.obj["pipeline"]
    result = pipeline.evaluate_version(version_id)
    _dump(result)


@cli.command("approve-and-deploy")
@click.option("--version-id", required=True)
@click.pass_context
def approve_and_deploy(ctx, version_id):
    """Governed approval AND deployment of a verified version (promotes to DEPLOYED)."""
    pipeline = ctx.obj["pipeline"]
    try:
        dep_id = pipeline.approve_and_deploy(version_id)
    except RuntimeError as exc:
        _dump({"approval": "DENIED", "reason": str(exc)})
        sys.exit(1)
    _dump({"deployment_id": dep_id, "status": "deployed", "approved": True})


@cli.command()
@click.option("--version-id", required=True)
@click.pass_context
def approve(ctx, version_id):
    """DEPRECATED alias for `approve-and-deploy` (approval + deployment).

    Retained for backward compatibility only. Emits a warning and delegates to
    the explicit `approve-and-deploy` command so the legacy behaviour is
    preserved while pointing operators at the clearer surface.
    """
    click.echo(
        "WARNING: `approve` is deprecated; use `approve-and-deploy` "
        "(it performs BOTH approval and deployment).",
        err=True,
    )
    ctx.invoke(approve_and_deploy, version_id=version_id)


@cli.command()
@click.option("--version-id", required=True)
@click.option("--approver", default="operator", show_default=True)
@click.pass_context
def request_approval(ctx, version_id, approver):
    """Run verification + trust gate and promote to APPROVED (no deploy)."""
    pipeline = ctx.obj["pipeline"]
    try:
        approval = pipeline.request_approval(version_id, approver)
    except RuntimeError as exc:
        _dump({"approval": "DENIED", "version_id": version_id, "reason": str(exc)})
        sys.exit(1)
    _dump(approval)


@cli.command()
@click.option("--model", "model_name", default=None)
@click.option("--version-id", default=None)
@click.option("--actor", default="operator", show_default=True)
@click.option("--target", "target_environment", default="production", show_default=True)
@click.pass_context
def request_deployment(ctx, model_name, version_id, actor, target_environment):
    """Governed deployment request: validate all gates, then promote via the registry."""
    pipeline = ctx.obj["pipeline"]
    try:
        result = pipeline.request_deployment(
            model_name=model_name,
            version_id=version_id,
            actor=actor,
            target_environment=target_environment,
        )
    except Exception as exc:
        details = getattr(exc, "details", None)
        _dump({"deployment": "DENIED", "reason": str(exc),
               **({"details": details} if details else {})})
        sys.exit(1)
    _dump(result)


@cli.command()
@click.option("--model", "model_name", required=True)
@click.pass_context
def deployment_status(ctx, model_name):
    """Show active deployment and serving health for a model."""
    pipeline = ctx.obj["pipeline"]
    active = pipeline.registry.active_deployment(model_name)
    if not active:
        click.echo(f"no active deployment for {model_name}", err=True)
        sys.exit(1)
    healthy, detail = True, ""
    try:
        from qsmlops.serving.service import ModelDeploymentService
        ModelDeploymentService(pipeline.registry).load(model_name)
    except Exception as exc:
        healthy, detail = False, f"{type(exc).__name__}: {exc}"
    latest = pipeline.registry.latest_trust(active["version_id"])
    _dump({"model": model_name, "active_deployment": active,
           "serving_healthy": healthy, "serving_detail": detail,
           "trust_decision": (latest or {}).get("trust_decision")})


@cli.command()
@click.option("--version-id", required=True)
@click.option("--actor", default="operator", show_default=True)
@click.option("--target", "target_environment", default="production", show_default=True)
@click.pass_context
def validate_deployment(ctx, version_id, actor, target_environment):
    """Dry-run every deployment gate without promoting."""
    pipeline = ctx.obj["pipeline"]
    report = pipeline.validate_deployment(version_id, actor=actor,
                                          target_environment=target_environment)
    _dump(report)


@cli.command()
@click.option("--version-id", required=True)
@click.option("--refresh", is_flag=True, help="Force a fresh evaluation before showing")
@click.pass_context
def trust(ctx, version_id, refresh):
    """Show the explainable trust report for a version."""
    pipeline = ctx.obj["pipeline"]
    if refresh:
        result = pipeline.registry.trust_evaluation(version_id, actor="cli")
        _dump(result.to_dict())
        return
    latest = pipeline.registry.latest_trust(version_id)
    if latest is None:
        click.echo(
            f"no trust evaluation recorded for {version_id}; run with --refresh",
            err=True,
        )
        sys.exit(1)
    _dump(latest)


@cli.command("registry")
@click.pass_context
def registry_status(ctx):
    """List all model versions with lifecycle state and persisted trust."""
    pipeline = ctx.obj["pipeline"]
    rows = []
    for v in pipeline.registry.list_versions():
        rows.append(
            {
                "version_id": v["version_id"],
                "model_name": v["model_name"],
                "version": v["version"],
                "state": v["state"],
                "trust_score": v.get("trust_score"),
                "trust_decision": v.get("trust_decision"),
            }
        )
    ok, msg = pipeline.ledger.verify_chain()
    _dump({"versions": rows, "ledger_chain_ok": ok})


@cli.command()
@click.option("--version-id", required=True)
@click.option("--reason", required=True)
@click.option("--actor", default="operator", show_default=True)
@click.pass_context
def revoke(ctx, version_id, reason, actor):
    """Revoke a version (audited; terminal state)."""
    pipeline = ctx.obj["pipeline"]
    try:
        pipeline.registry.revoke(version_id, actor, reason)
    except Exception as exc:
        _dump({"revoked": False, "error": str(exc)})
        sys.exit(1)
    _dump({"version_id": version_id, "revoked": True, "reason": reason})


@cli.command()
@click.option("--model", "model_name", required=True)
@click.pass_context
def deploy(ctx, model_name):
    """Deploy the latest approved version of a model.

    Uses the same governed deployment service as the REST API so every gate
    (identity, SoD, crypto, trust eligibility, environment, policy) runs
    before the registry promotes the version.
    """
    pipeline = ctx.obj["pipeline"]
    try:
        result = pipeline.request_deployment(model_name=model_name, actor="cli")
    except Exception as exc:
        details = getattr(exc, "details", None)
        _dump({"deployment": "DENIED", "reason": str(exc),
               **({"details": details} if details else {})})
        sys.exit(1)
    _dump(result)


@cli.command()
@click.option("--model", "model_name", required=True)
@click.option("--mse", type=float, default=None)
@click.option("--r2", type=float, default=None)
@click.pass_context
def health_check(ctx, model_name, mse, r2):
    """Observe deployed model health; supervisor decides recovery."""
    pipeline = ctx.obj["pipeline"]
    degraded = {}
    if mse is not None:
        degraded["mse"] = mse
    if r2 is not None:
        degraded["r2"] = r2
    result = pipeline.health_check(model_name, degraded if degraded else None)
    _dump(result)


@cli.command()
@click.option("--model", "model_name", required=True)
@click.pass_context
def rollback(ctx, model_name):
    """Roll back the active deployment to the previous version."""
    pipeline = ctx.obj["pipeline"]
    prev = pipeline.registry.rollback(model_name, "cli")
    if prev is None:
        click.echo("no previous version to roll back to", err=True)
        sys.exit(1)
    _dump({"restored_version_id": prev, "status": "rolled_back"})


@cli.command()
@click.pass_context
def audit_ledger(ctx):
    """Verify the hash chain of the evidence ledger."""
    pipeline = ctx.obj["pipeline"]
    ok, msg = pipeline.ledger.verify_chain()
    head = pipeline.ledger.head()
    _dump({"chain_ok": ok, "message": msg, "head": head})


@cli.command("audit-ledger-packets")
@click.pass_context
def audit_ledger_packets(ctx):
    """Verify that every ledger-committed packet body is present and digest-matched (F1)."""
    pipeline = ctx.obj["pipeline"]
    ids = pipeline.ledger.list_packet_ids()
    failures: list[dict] = []
    for pid in ids:
        ok, msg = pipeline.ledger.verify_packet(pid)
        if not ok:
            failures.append({"packet_id": pid, "ok": ok, "detail": msg})
    _dump({"total_packets": len(ids), "failures": failures, "all_intact": len(failures) == 0})


@cli.command("show-packet")
@click.option("--packet-id", required=True, help="VerificationPacket ID to retrieve")
@click.pass_context
def show_packet(ctx, packet_id):
    """Retrieve a persisted VerificationPacket by packet_id (F1)."""
    pipeline = ctx.obj["pipeline"]
    pkt = pipeline.ledger.get_packet(packet_id)
    if pkt is not None:
        _dump(pkt.to_dict())
        return
    entry = pipeline.ledger.find_by_packet(packet_id)
    if entry is None:
        _dump({"error": "packet_id not found", "packet_id": packet_id})
        sys.exit(1)
    ok, msg = pipeline.ledger.verify_packet(packet_id)
    _dump({"error": msg, "packet_id": packet_id})
    sys.exit(1)


@cli.command()
@click.option("--model", "model_name", required=True)
@click.option("--artifact-digest", required=True)
@click.pass_context
def redteam(ctx, model_name, artifact_digest):
    """Run the red team agent against a registered artifact."""
    pipeline = ctx.obj["pipeline"]
    context = {
        "subject_id": model_name,
        "artifact_digest": artifact_digest,
        "probe_inputs": [[0.1, -0.2], [0.5, 0.3], [-0.4, 0.6], [1.0, -1.0], [0.0, 0.0]],
    }
    from qsmlops.agents.redteam import RedTeamAgent

    agent = RedTeamAgent(pipeline.artifacts)
    obs = agent.observe(context)
    _dump(obs.to_dict())


@cli.command()
@click.option("--owner", default="producer")
@click.pass_context
def rotate_keys(ctx, owner):
    """Rotate the active signing key for a producer."""
    pipeline = ctx.obj["pipeline"]
    new_key = pipeline.keystore.rotate_signer(owner)
    _dump({"rotated_to": new_key})


@cli.command()
@click.pass_context
def status(ctx):
    """Show platform status: key inventory, registry summary, ledger head."""
    pipeline = ctx.obj["pipeline"]
    keys = [
        {"key_id": r.key_id, "role": r.role, "algo": r.algorithm_id, "version": r.version, "status": r.status}
        for r in pipeline.keystore.list_records(include_inactive=True)
    ]
    models = pipeline.registry.list_versions()
    ok, msg = pipeline.ledger.verify_chain()
    _dump(
        {
            "keys": keys,
            "models": models,
            "ledger": {"chain_ok": ok, "message": msg, "head": pipeline.ledger.head()},
        }
    )


if __name__ == "__main__":
    cli()