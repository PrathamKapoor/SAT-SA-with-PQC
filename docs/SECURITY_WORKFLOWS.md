# Security Workflows

End-to-end flows showing where cryptographic guarantees are produced and
enforced.

## 1. Provision → Train → Register

```
provision_dataset        dataset bytes → ArtifactStore (SHA3-256 digest)
                         name→digest index + QML-BOM entry
train_and_register       train (reference or adapter framework)
                         build QML-BOM: dataset / code / artifact / framework
                         new_passport(...) binds digests + metrics + env
                         passport.sign(keystore, agility, signer_owner)
                         registry.register(passport, artifact_bytes, bom_digest)
```

## 2. Verify → Approve → Deploy

```
evaluate_version         all agents observe; CRITICAL/HIGH findings become
                         security checks in the verification packet
approve_and_deploy       refuses unless packet decision == VERIFIED;
                         registry state machine enforces gates and
                         separation of duties (signer ≠ verifier)
```

## 3. Serve

`ModelDeploymentService.load(model)`:

1. resolve active deployment → version record
2. refuse any state other than `DEPLOYED`
3. load artifact bytes (corrupted/missing → `ServingError`)
4. verify passport signature against the trust anchor
5. classify key problems: revoked → `ServingError("revoked")`,
   expired → `ServingError("expired")`, forged/zeroed signature →
   `KeyError("not found")`
6. deserialize + cache; every `predict` appends an `inference` audit event.

## 4. Monitor → Recover (self-healing)

```
health_check(model, degraded_metrics?, current_data?)
  ├─ drift engine: PSI/KS feature drift + prediction drift
  ├─ context = {passport, bom, keystore, metrics, drift_summary}
  └─ supervisor.run_cycle:
       Observe   agents produce evidence-backed findings
       Detect    aggregate risk (severity-weighted)
       Reason    facts → PolicyEngine (priority-ordered rules)
       Act       guarded handler per Decision
       Verify    postcondition checked against registry state
       Learn     LearningStore escalates after repeated failed recoveries
```

Decisions: ACCEPT · DEPLOY · RETRAIN · ROLLBACK · QUARANTINE ·
ROTATE_KEYS · BLOCK_DEPLOYMENT · ESCALATE.

Drift findings never trigger hard quarantine by themselves — they route to
the dedicated `rollback_on_critical_drift` rule so a drifted-but-signed
model is rolled back or retrained rather than quarantined.

## 5. Policy set management (hot reload)

```python
from qsmlops.security.policies import PolicyRegistry

registry = PolicyRegistry(config_dir="configs")
registry.register("supervisor", "configs/policies.json")
engine = registry.engine_for("supervisor")   # auto-reloads on file change
```

* JSON or YAML by extension.
* A broken document never replaces the last known-good rule set;
  `pset.last_error` records the failure.
* `write_default_document(path, doc)` seeds an initial file.

## 6. Audit

Every workflow step lands in the hash-chained EvidenceLedger: lifecycle
events (`dataset_provisioned`, `inference`, `drift_check`, …), verification
packets with per-check results, supervisor decisions with policy rationale,
and identity/audit service events (`identity.created`,
`identity.status.revoked`, …). Ledger integrity is verified with
`ledger.verify_chain()`.
