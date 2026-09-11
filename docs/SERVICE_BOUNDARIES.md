# Service Boundaries\n\nEach logical layer in the platform is isolated behind an explicit contract.\n\n| Layer | Primary Contract | Example Implementation | Future Extension |
|-------|------------------|------------------------|------------------|
| User Interaction | `interfaces.UserInterface` | FastAPI endpoint, CLI command | Custom UI frameworks |
| API Gateway | `api.gateway.router` + middleware | FastAPI router with auth hooks | Service mesh integration |
| IAM | `identity.models.*` & `identity.service.IdentityService` | In‑memory store (current) | External IdP, OIDC |
| MLOps Orchestration | `mlops.*` contracts | Self‑healing pipeline (current) | Distributed training, Spark |
| Workflow Engine | `workflow.Engine` | Simple state machine (current) | BPMN, Camunda |
| Trust Layer | `trust.models.TrustedArtifact` | Artifact metadata (current) | Quantum‑secure attestation |
| Security Layer | `security.crypto.*` services | Stub methods (current) | ML‑KEM, ML‑DSA implementations |
| Agents | `agents.base.BaseAgent` & registry | Data/Performance agents (current) | Plug‑in agent marketplace |
| Supervisor | `supervisor.AdaptiveSupervisor` | Decision logic (current) | Policy DSL, ML‑based risk scoring |
| Monitoring | `monitoring.metrics.MetricsCollector` | In‑process collector (current) | Prometheus, OpenTelemetry |
| Events | `events.bus.EventBus` | In‑process publish/subscribe (current) | Kafka, NATS |
\nThese boundaries ensure that swapping one implementation for another does not impact dependent layers.\n