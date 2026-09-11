# Cryptographic Identity

Platform principals are first-class governed objects, authenticated by
key material rather than passwords.

## Identity model (`qsmlops/security/identity/models.py`)

`Identity` extends `TrustedObject` (id / owner / version / hash / signature /
verification vocabulary shared with every other governed entity).

| Field | Meaning |
|-------|---------|
| `kind` | `human` · `service` · `agent` |
| `name`, `owner` | unique per `(kind, name)`; owner is accountable principal |
| `role` | named permission set from the role registry |
| `permissions` | concrete action grants (e.g. `model.verify`) |
| `status` | `active` · `inactive` · `revoked` |

Agents always receive least-privilege roles; `agent.act` is intentionally
never granted by a built-in role.

## Lifecycle (`qsmlops/security/identity/service.py`)

Creation is the only mutate path; every change emits an `AuditEvent`
(`identity.created`, `identity.status.<status>`,
`identity.permissions.granted|revoked`).

```python
identity = identities.create_identity(
    kind="human", name="alice", owner="security-team", role="ml-engineer"
)
identities.authorize(identity, "model.train")   # raises PermissionDeniedError otherwise
identities.revoke(identity.id, reason="offboarding")  # terminal state
```

Key issuance: non-agent identities optionally get an ML-DSA signing keypair
provisioned in the KeyStore at creation time (best-effort).

## Authorization semantics

* Inactive or revoked identities fail authorization.
* Revocation is irreversible — a revoked identity cannot be reactivated.
* Unknown roles are rejected both at creation and at check time.
