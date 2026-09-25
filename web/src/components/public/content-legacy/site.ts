/**
 * Real content for the SAT-SA landing page, sourced from github.com/PrathamKapoor/SAT-SA-with-PQC:
 * README.md, docs/CLAIMS.md, docs/AGENT_INVENTORY.md, docs/SATSA_SYSTEM_ARCHITECTURE.md,
 * docs/TRUST_MODEL.md, docs/roadmap-status.md, and a live run of the committed demo (scripts/serve_ui.py)
 * on 2026-09-12. Numbers are cited with their source so nothing here drifts from the repo's own
 * honesty discipline ("never claim more than a test or a live run proves").
 */

export const GITHUB_URL = "https://github.com/PrathamKapoor/SAT-SA-with-PQC";

export const navContent = {
  homeHref: "#",
  logoLabel: "SAT-SA home",
  links: [
    { label: "Supervisory Workbench", href: "/workbench" },
    { label: "Mission", href: "#mission" },
    { label: "See it work", href: "#see-it-work" },
    { label: "Pipeline", href: "#pipeline" },
    { label: "Agents", href: "#agents" },
    { label: "Trust", href: "#trust" },
    { label: "Screens", href: "#screenshots" },
    { label: "Validation", href: "#validation" },
  ],
  cta: { label: "GitHub", href: GITHUB_URL, external: true },
};

export const heroContent = {
  eyebrow: "SIH 26157 · Supervisory analytics",
  titleLines: ["Supervisory", "analytics", "for SOC", "assessment."],
  lede: ["Analyse SOC evidence.", "Find what needs supervisory attention."],
  primaryCta: { label: "Explore SAT-SA", href: "/workbench/overview" },
  secondaryCta: { label: "See how it works", href: "#pipeline" },
  steps: ["INGEST", "ANALYSE", "PRIORITISE", "REVIEW"],
  /** From a live run of the committed demo dataset, scripts/serve_ui.py, 2026-09-12. */
  demoStats: [
    { value: "7", label: "entities" },
    { value: "12", label: "analysis runs" },
    { value: "85", label: "signal findings" },
    { value: "Verified", label: "trust chain" },
  ],
};

export const identityContent = {
  eyebrow: "System identity",
  title: "What SAT-SA is, and is not.",
  is: [
    "A periodic, offline, evidence-driven supervisory analytics system.",
    "Human-supervised: agents observe and recommend, a human examiner decides. Terminal authority, append-only audit.",
    "Post-quantum trusted: every run and finding signed with ML-DSA-65, hash-chained evidence ledger, deterministic content digests.",
    "Air-gapped by design: zero network calls anywhere in the pipeline.",
  ],
  isNot: [
    "Not a SIEM, and not a SOC replacement.",
    "Not a real-time monitor or a continuous telemetry collector.",
    "Not a national monitoring system.",
    "Not an autonomous supervisory authority: a human is always the terminal decision-maker.",
  ],
};

/**
 * Engineering, at a glance. "source" is shown as a footnote so every number stays traceable.
 */
export const statsContent = {
  eyebrow: "By the numbers",
  title: "Engineering, at a glance.",
  stats: [
    { value: 32, suffix: "", label: "Supervisory agents", detail: "9 retained MLOps + 23 SAT-SA" },
    { value: 16, suffix: "", label: "Analytical workers", detail: "in the default run" },
    { value: 7, suffix: "", label: "Risk dimensions", detail: "decomposable, explainable" },
    { value: 1000, suffix: "+", label: "Tests", detail: "full suite, ~5–10 min" },
    { value: 92.5, suffix: "%", label: "Line coverage", detail: "satsa/ + evaluation/, measured" },
    { value: 0, suffix: "", label: "Network calls", detail: "verified offline, full pipeline" },
  ],
  source: "docs/CLAIMS.md, README.md. Reproduce with `pytest tests/ -q` and `coverage report`.",
};

export const pipelineContent = {
  eyebrow: "Architecture",
  title: "From submission to supervisory intelligence.",
  intro:
    "Every SAT-SA workflow terminates at the human supervisor's recorded decision, and at the cryptographic integrity layer that proves the evidence was not tampered with.",
  stages: [
    {
      num: "01",
      icon: "ingest",
      title: "Ingest & normalize",
      body: "Normalize CSE submissions.",
    },
    {
      num: "02",
      icon: "analyze",
      title: "Analyze",
      body: "Detect operational signals.",
    },
    {
      num: "03",
      icon: "correlate",
      title: "Correlate & score risk",
      body: "Fuse signals into explainable risk.",
    },
    {
      num: "04",
      icon: "recommend",
      title: "Prioritize & recommend",
      body: "Focus supervisory review.",
    },
    {
      num: "05",
      icon: "review",
      title: "Human review",
      body: "The examiner records the decision.",
    },
    {
      num: "06",
      icon: "verify",
      title: "TRUST-SAT verification",
      body: "Prove evidence integrity.",
    },
  ] as const,
  screenshot: {
    src: "/sites/sat-sa-with-pqc/root/screenshots/review-queue.jpeg",
    alt: "SAT-SA Review Queue: ranked review samples with priority reason, recommended action and disposition controls",
    caption: "Review Queue: the pipeline ends at a recorded human decision.",
  },
};

export const agentsContent = {
  eyebrow: "The 32-agent model",
  title: "32 agents, one supervisory fabric.",
  intro:
    "32 agents is a consequence of responsibility separation, not a target. It grew from 26 in phase P25, then 31 to 32 in phase P26. Every agent implements the same contract, observe(context) → Observation, and none may make an irreversible supervisory decision on its own.",
  groups: [
    {
      count: 9,
      label: "Retained MLOps agents",
      pkg: "qsmlops/",
      note: "Unchanged: they govern the ML platform itself.",
      items: [
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
      count: 23,
      label: "SAT-SA supervisory agents",
      pkg: "satsa/",
      note: "Orchestrated by SAT-SA's own Observe → Reason → Act → Verify → Learn engine.",
      items: [
        "EntityAssetResolution",
        "Ingestion",
        "Normalization",
        "ExecutionGap",
        "NegativeSpace",
        "WorkflowReconstruction",
        "Anomaly",
        "PeerBenchmark",
        "CoverageGap",
        "Drift",
        "CrossEntityInsights",
        "CaseSimilarity",
        "EvidenceCompleteness",
        "CorrelationSignalFusion",
        "EntityRiskScoring",
        "Prioritization",
        "Recommendation",
        "ReviewWorkflow",
        "TrustProvenance",
        "EvidenceAssembly",
        "MetaAudit",
        "ReportGeneration",
        "Validation",
      ],
    },
  ],
  screenshot: {
    src: "/sites/sat-sa-with-pqc/root/screenshots/findings.jpeg",
    alt: "SAT-SA Findings page: evidence-backed findings produced by the supervisory agents, with pattern, rationale and entity context",
    caption: "What the agents produce: evidence-backed findings.",
  },
  source: "docs/AGENT_INVENTORY.md",
};

export const trustContent = {
  eyebrow: "Cryptographic integrity",
  title: "TRUST-SAT is the foundation.",
  intro:
    "Every persisted record (source submission, observation, finding, risk profile, recommendation, human decision) is signed with post-quantum ML-DSA-65 and bound to a hash-chained evidence ledger. Verification re-derives the canonical digest from the live row and confirms the signature.",
  pillars: [
    { label: "Signature", value: "ML-DSA-65", detail: "NIST FIPS 204, over the canonical SHA3-256 digest" },
    { label: "Digest", value: "SHA3-256", detail: "canonical JSON: sort_keys, ensure_ascii=False, no whitespace" },
    { label: "Ledger", value: "Hash-chain", detail: "append-only; deletion and forged insertion both detected" },
    { label: "Authority", value: "Human", detail: "terminal decision-maker; recommendation ≠ decision" },
  ],
  claim:
    "Trust claim is detection of tampering at verification time, not tamper-proofness, bounded by filesystem-level trust, with no external anchor.",
  screenshot: {
    src: "/sites/sat-sa-with-pqc/root/screenshots/trust-sat.jpeg",
    alt: "SAT-SA TRUST-SAT and Audit page: ML-DSA-65 posture, hash-chained evidence ledger, data lineage and review-decision ledger",
    caption: "TRUST-SAT & Audit: signed lineage and the decision ledger.",
  },
};

export const validationContent = {
  eyebrow: "Validation",
  title: "Per-layer, never one accuracy number.",
  intro:
    "Statistical analytics are valid. Deterministic rules are valid. Robust statistics are valid. ML only where it adds actual value, and every claim below is labeled by what actually proves it.",
  rows: [
    {
      label: "Synthetic ground truth",
      status: "verified",
      detail: "10 deterministic scenarios, generated outside the analytical pipeline, compared after the fact.",
    },
    {
      label: "Fresh-database end-to-end",
      status: "verified",
      detail: "A hand-crafted submission with non-canonical column names ingested with 0 rejections, real findings produced.",
    },
    {
      label: "Workload reduction",
      status: "simulated",
      detail: "3.75× lift reviewing the top 10% of the queue: an empirical, 500-trial measurement, not a claim about real analyst time saved.",
    },
    {
      label: "Scaling benchmark",
      status: "verified",
      detail: "Measured at 5 / 10 / 25 / 50 CSE. 100 / 1000 CSE targets are pending.",
    },
    {
      label: "Public-benchmark framework",
      status: "verified, scoped",
      detail: "12 controlled scenarios, schema-compatible with CIC-IDS2017 / Splunk BOTS, run on hand-built sample rows, not the actual downloaded datasets.",
    },
    {
      label: "Expert review",
      status: "pending",
      detail: "The instrument is built (per-finding YES/NO/UNLABELED); real reviewer responses are not yet collected.",
    },
  ],
  source: "docs/CLAIMS.md: every row there cites a test file or an explicit pending/unverified label.",
};

export const limitationsContent = {
  eyebrow: "Honesty discipline",
  title: "What this doesn't claim.",
  intro: "Straight from the README's own limitations section, never fabricated, never quietly dropped.",
  items: [
    "Risk weights are a starting hypothesis pending domain-expert calibration, never a claimed-final model.",
    "PQC is pure-Python (dilithium-py / kyber-py), not side-channel hardened; a liboqs migration is the stated path.",
    "No PKCS#11 hardware token supports ML-DSA / ML-KEM yet, industry-wide. The platform fails closed and self-certifies rather than pretending otherwise.",
    "SQLite's single-writer boundary is documented, not hidden.",
    "Public-benchmark adapters are schema-compatible with CIC-IDS2017 / Splunk BOTS but have not been run against the real downloaded dataset files.",
  ],
};

export const footerContent = {
  repo: { label: "SAT-SA-with-PQC", href: GITHUB_URL },
  packages: [
    { name: "satsa", version: "0.16.0-phase52-ui" },
    { name: "qsmlops", version: "0.1.0" },
  ],
  license: { label: "MIT License", author: "Pratham Kapoor" },
  program: "Smart India Hackathon · SIH 26157 · NCIIPC",
};
