import type {
  AgentGroup,
  DetectorGroup,
  LimitationItem,
  RepoTreeEntry,
  StatItem,
  TrustCell,
} from "@/types/sat-sa";

export const NAV_LINKS = [
  { label: "Architecture", href: "#architecture" },
  { label: "Agents", href: "#agents" },
  { label: "Analytics", href: "#analytics" },
  { label: "TRUST-SAT", href: "#trust" },
  { label: "Validation", href: "#validation" },
  { label: "Repo", href: "#repo" },
] as const;

export const GITHUB_URL = "https://github.com/PrathamKapoor/SAT-SA-with-PQC";

export const HERO_STATS: StatItem[] = [
  { value: "26", label: "Supervisory agents" },
  { value: "14", label: "Analytical workers" },
  { value: "930+", label: "Tests" },
  { value: "0", label: "Network calls" },
];

export const MISSION_IS = [
  "A periodic, offline, evidence-driven supervisory analytics system",
  "A human-supervised instrument: agents observe and recommend, a human examiner decides (terminal authority, append-only audit)",
  "Post-quantum trusted: every run and finding signed with ML-DSA-65, hash-chained evidence ledger, deterministic content digests",
  "Air-gapped by design: zero network calls in the full pipeline",
];

export const MISSION_IS_NOT = [
  "A SIEM",
  "A SOC replacement",
  "A real-time monitor",
  "A national monitoring system",
  "A continuous telemetry collector",
  "An autonomous supervisory authority",
];

export const ARCHITECTURE_FLOW = [
  { label: "Security Data", sub: "alerts · cases · investigations · escalations · dispositions · assets" },
  { label: "ML / Analytics", sub: "14 analytical workers, robust statistics" },
  { label: "Supervisory Agents", sub: "Detect · Correlate · Assess / Reason" },
  { label: "Threat / Risk Finding", sub: "7-dimension decomposable risk" },
  { label: "Recommendation", sub: "bounded recommendation engine" },
  { label: "Human Supervisor", sub: "terminal authority" },
  { label: "Action / Decision", sub: "recorded, append-only" },
];

export const TRUST_FOUNDATION = [
  { label: "PQC Signatures", value: "ML-DSA-65 signing", meta: "over canonical SHA3-256 digests" },
  { label: "Provenance", value: "source → decision", meta: "source, record, observation, finding, risk, recommendation, decision" },
  { label: "Hash-chain", value: "append-only ledger", meta: "tamper-evident evidence ledger" },
];

export const AGENT_GROUPS: AgentGroup[] = [
  {
    family: "MLOps",
    count: 9,
    description: "Retained MLOps agents (qsmlops/) — unchanged; they govern the ML platform itself.",
    agents: [
      "Data",
      "Performance",
      "Security",
      "QuantumSecurity",
      "RedTeam",
      "Governance",
      "IncidentResponse",
      "Optimization",
      "TrainingOptimization",
    ],
  },
  {
    family: "SAT-SA",
    count: 17,
    description: "SAT-SA supervisory agents (satsa/) — observe and recommend; never decide independently.",
    agents: [
      "Ingestion",
      "Normalization",
      "ExecutionGap",
      "NegativeSpace",
      "Anomaly",
      "PeerBenchmark",
      "CoverageGap",
      "Drift",
      "CrossEntityInsights",
      "CaseSimilarity",
      "EvidenceCompleteness",
      "Fusion",
      "Prioritization",
      "Recommendation",
      "ReviewWorkflow",
      "TrustProvenance",
      "Validation",
    ],
  },
];

export const AGENT_CONTRACT =
  "Every agent implements the common contract observe(context) → Observation with severity, confidence, scope, subjects, evidence_refs, rationale, statistics, threshold, limitations, recommended_action, analysis_period, and provenance.";

export const SUPERVISOR_ENGINE =
  "One generalized supervisor engine (satsa/supervisor/engine.py) runs Observe → Reason → Act → Verify → Learn with two pluggable, lexically disjoint decision vocabularies.";

export const DECISION_VOCABULARIES = [
  {
    name: "SAT-SA",
    note: "all require human authority",
    actions: [
      "SATSA_SURFACE",
      "SATSA_INSPECT",
      "SATSA_REQUEST_EVIDENCE",
      "SATSA_ESCALATE_FOR_REVIEW",
      "SATSA_DEFER",
      "SATSA_ACCEPT",
      "SATSA_CLOSE_REVIEW",
    ],
  },
  {
    name: "MLOps",
    note: "policy-driven proposals",
    actions: [
      "ACCEPT",
      "DEPLOY",
      "RETRAIN",
      "QUARANTINE",
      "ROTATE_KEYS",
      "BLOCK_DEPLOYMENT",
      "ESCALATE",
      "ROLLBACK",
    ],
  },
];

export const ANALYTICS_GROUPS: DetectorGroup[] = [
  {
    title: "Execution-gap detectors (6)",
    items: [
      "Fast closure",
      "Ack-without-investigation",
      "Critical-without-escalation",
      "Repeated investigation",
      "Recurring-without-remediation",
      "Metric gaming",
    ],
  },
  {
    title: "Negative space (6 rules)",
    items: ["Robust anomaly statistics", "Peer benchmarking (trimmed statistics)", "Coverage gap", "Drift", "Cross-entity insights", "Case similarity"],
  },
];

export const RISK_DIMENSIONS = [
  "execution_gap",
  "peer_deviation",
  "detection_gap",
  "negative_space",
  "anomaly",
  "investigation_quality",
  "escalation_discipline",
];

export const RECOMMENDATION_ACTIONS = [
  "INSPECT_INVESTIGATION",
  "CHECK_ESCALATION_PATH",
  "VERIFY_MONITORING_COVERAGE",
  "COMPARE_WITH_PEERS",
  "REQUEST_MISSING_EVIDENCE",
  "REVIEW_METRIC_DEFINITION",
  "INSPECT_ROOT_CAUSE_REMEDIATION",
  "REVIEW",
];

export const TRUST_CELLS: TrustCell[] = [
  {
    label: "PQC signatures",
    value: "ML-DSA-65",
    meta: "over canonical SHA3-256 digests",
  },
  {
    label: "Provenance",
    value: "source → decision",
    meta: "source, record, observation, finding, risk, recommendation, decision",
  },
  {
    label: "Hash-chain ledger",
    value: "append-only",
    meta: "tamper-evident evidence ledger",
  },
  {
    label: "Evidence integrity",
    value: "live re-derivation",
    meta: "verification re-derives digests from live rows; any tamper is detected",
  },
];

export const TRUST_CLAIM =
  "Trust claim is detection of tampering at verification time, not tamper-proofness.";

export const VALIDATION_ITEMS = [
  "Synthetic ground truth: 10 deterministic scenarios (healthy, execution-gap, negative-space, anomaly, peer-deviation, mixed, borderline, noisy, missing-evidence, conflicting-evidence) generated outside the analytical execution, compared after the fact",
  "Expert labels: layer, is_signal, category, severity, expected action, rationale, confidence, reviewer, timestamp",
  "Offline guarantee, scaling benchmark (5/10/25/50 CSE), peer robustness, trust stress (every mutation rejected or classified)",
];

export const REPO_TREE: RepoTreeEntry[] = [
  { name: "satsa/", note: "SAT-SA supervisory analytics (the product)" },
  { name: "qsmlops/", note: "reusable MLOps trust infrastructure (retained)" },
  { name: "evaluation/", note: "workload-reduction / prioritization-lift experiment" },
  { name: "tests/", note: "930+ tests, incl. per-layer, e2e, offline, trust stress" },
  { name: "scripts/", note: "demo dataset builder, scaling benchmark, SoftHSM2 bootstrap" },
  { name: "docs/", note: "phase docs, roadmap, deployment, claims, trust model" },
  { name: "demo.py", note: "SAT-SA end-to-end demonstration" },
  { name: "Dockerfile", note: "single-process container" },
];

export const INSTALL_STEPS = [
  "python -m venv .venv",
  "# Windows: .venv\\Scripts\\activate   |   Linux/Mac: source .venv/bin/activate",
  "pip install -r requirements.txt",
  "python -m compileall satsa qsmlops",
  "python -m pytest tests/ -q",
];

export const DEMO_STEPS = [
  "python demo.py            # full SAT-SA story: 5 CSEs → findings → risk → trust → review",
  "python scripts/serve_ui.py --db ./satsa.db --trust-key-dir ./keys --port 8000",
  "# open http://127.0.0.1:8000/",
];

export const LIMITATIONS: LimitationItem[] = [
  {
    title: "Risk weights are a starting hypothesis",
    detail: "Pending domain-expert calibration — never a claimed-final model.",
  },
  {
    title: "PQC is pure-Python",
    detail: "dilithium-py / kyber-py, not side-channel hardened; liboqs migration is the stated path.",
  },
  {
    title: "No PKCS#11 token supports ML-DSA/ML-KEM",
    detail: "Industry-wide hardware limitation; the platform fails closed and self-certifies.",
  },
  {
    title: "SQLite single-writer boundary",
    detail: "Documented, not hidden.",
  },
  {
    title: "Expert validation scaffolded",
    detail: "Framework + synthetic ground truth complete; production expert-label volume pending.",
  },
  {
    title: "Cross-entity insights + drift honestly abstain",
    detail: "insufficient_data for an entity's first assessment or the first entity in a shared assessment — never fabricate.",
  },
  {
    title: "CI and the Dockerfile are unverified",
    detail: "Written and consistent with locally-verified commands, but neither has executed on GitHub Actions or a real Docker daemon.",
  },
];

export const CLI_EXAMPLE = `sat-sa --db ./satsa.db --trust-key-dir ./keys ingest CSE-X ./sub \\
  --period-start 1735689600 --period-end 1738281600
sat-sa --db ./satsa.db --trust-key-dir ./keys analyze <entity> <assessment>
sat-sa --db ./satsa.db risk <entity>
sat-sa --db ./satsa.db prioritize [--run-id <run>]
sat-sa --db ./satsa.db --trust-key-dir ./keys verify <run>
sat-sa --db ./satsa.db review --finding-id <f> --action confirm --reason "..."`;
