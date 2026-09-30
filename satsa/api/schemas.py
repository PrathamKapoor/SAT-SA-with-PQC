"""Deliberate public schemas; database fields are never serialized wholesale."""

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class Schema(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)


class Input(Schema):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    # PostgreSQL text cannot hold NUL; reject it as invalid input, not a 500.
    @field_validator("*", mode="after")
    @classmethod
    def _no_nul(cls, value):
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("NUL characters are not allowed")
        return value


class Page(Schema, Generic[T]):
    items: list[T]
    limit: int
    offset: int
    has_more: bool


class ErrorBody(Schema):
    code: str
    message: str
    request_id: str
    details: list[dict[str, Any]] = []


class Error(Schema):
    error: ErrorBody


class Login(Input):
    credential: str = Field(min_length=1, max_length=512)


class Session(Schema):
    identity_id: str
    name: str
    role: str
    user_id: str
    expires_at: float | None = None
    csrf_token: str | None = None


class Organization(Schema):
    id: str
    name: str
    status: str
    role: str


class OrganizationInput(Input):
    name: str = Field(min_length=1, max_length=200)


class MemberInput(Input):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    role: Literal[
        "satsa_viewer",
        "satsa_analyst",
        "satsa_supervisor",
        "satsa_auditor",
        "satsa_admin",
    ]


class Member(Schema):
    id: str
    identity_id: str
    name: str
    email: str
    role: str
    status: str


class Invitation(Member):
    credential: str


class EntityInput(Input):
    display_name: str = Field(min_length=1, max_length=200)
    sector: str = Field(default="", max_length=100)
    environment_class: str = Field(default="", max_length=100)


class Entity(EntityInput):
    model_config = ConfigDict(extra="ignore")
    id: str
    organization_id: str
    created_at: float


class AssessmentInput(Input):
    entity_id: str
    period_start: float
    period_end: float


class Assessment(AssessmentInput):
    model_config = ConfigDict(extra="ignore")
    id: str
    organization_id: str
    status: str
    created_at: float


class SubmissionInput(Input):
    assessment_id: str


class Submission(Schema):
    id: str
    organization_id: str
    entity_id: str
    assessment_id: str
    ingest_status: str
    created_at: float


class Version(Schema):
    id: str
    organization_id: str
    submission_id: str
    version: int
    status: str
    created_at: float
    snapshot_digest: str | None = None


class Artifact(Schema):
    id: str
    submission_version_id: str
    category: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha3_256_digest: str
    created_at: float
    storage_status: Literal["uploading", "stored", "failed"] = "stored"


class RunInput(Input):
    submission_version_id: str
    execution_mode: Literal["standard", "graph"] = "graph"


class Step(Schema):
    worker_name: str
    status: str
    attempt: int
    started_at: float | None = None
    finished_at: float | None = None
    error: str = ""


class Run(Schema):
    id: str
    organization_id: str
    entity_id: str
    assessment_id: str
    submission_id: str
    submission_version_id: str
    status: str
    requested_at: float
    started_at: float | None = None
    finished_at: float | None = None
    execution_id: str
    execution_mode: str
    review_required: bool
    current_stage: str
    progress_total: int
    progress_completed: int
    retry_count: int
    error: str = ""
    error_code: str = ""
    steps: list[Step]


class DecisionInput(Input):
    action: Literal["confirm", "dismiss", "escalate"]
    reason: str = Field(default="", max_length=4000)


class Decision(Schema):
    id: str
    run_id: str
    finding_id: str | None = None
    user_id: str
    principal_identity_id: str
    action: str
    reason: str
    content_digest: str
    review_context_digest: str | None = None
    created_at: float


class Finding(Schema):
    id: str
    run_id: str
    observation_id: str
    rule_or_category: str
    rationale: str
    statistic: float | None = None
    effect: float | None = None
    threshold: float | None = None
    limitations: str = ""
    state: str
    confidence: dict[str, Any] | None
    evidence_refs: list[str]
    scoped_subjects: list[Any]
    content_digest: str
    created_at: float


class Recommendation(Schema):
    id: str
    finding_id: str
    action: str
    recommendation: dict[str, Any]
    content_digest: str
    created_at: float


class Evidence(Schema):
    source_record_id: str
    artifact_id: str
    record_id: str
    category: str
    locator: str
    format: str
    file_digest: str
    original_record_digest: str
    canonical_record_digest: str


class Verification(Schema):
    run_id: str
    status: Literal["verified", "inconsistent", "not_finalized", "unavailable"]
    verified_at: float
    code: str
    message: str


class Receipt(Schema):
    id: str | int
    organization_id: str
    run_id: str
    decision_id: str
    schema_version: int
    state: str
    key_id: str
    algorithm_id: str
    content_digest: str
    created_at: float
    ledger_entry_hash: str
    signature_b64: str
    public_key_b64: str


class AuditEvent(Schema):
    event_id: str
    timestamp: float
    actor: str
    action: str
    resource: str
    result: str


class Validation(Schema):
    status: str
    errors: list[Any] = []
    warnings: list[Any] = []
    version_id: str
    categories: dict[str, Any] = {}
    totals: dict[str, int]
    artifact_digests: dict[str, str]
    validator_version: str | None = None
    created_at: float | None = None


class Risk(Schema):
    profile: dict[str, Any]
    content_digest: str
    algorithm_version: str
    created_at: float


class EntityPriority(Schema):
    entity_id: str
    run_id: str
    run_status: str
    priority_score: float
    risk_score: float
    confidence_bucket: str
    rationale: str
    top_dimensions: list[str]
    high_signal_count: int


class MLDatasetInput(Input):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    data_origin: Literal["organizational", "synthetic", "controlled", "external"]


class MLDataset(Schema):
    id: str
    name: str
    version: int
    data_origin: str
    source: str
    feature_version: str
    schema_version: int
    record_count: int
    label_counts: dict[str, int]
    content_digest: str
    status: str
    validation: dict[str, Any] | None = None
    lineage: dict[str, Any]
    created_by: str
    created_at: float
    validated_at: float | None = None


class MLJob(Schema):
    id: str
    kind: str
    subject_id: str
    status: str
    params: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str
    attempt_count: int
    max_attempts: int
    requested_by: str
    created_at: float
    updated_at: float
    completed_at: float | None = None


class MLTrainingInput(Input):
    dataset_id: str = Field(min_length=1, max_length=128)
    hyperparameters: dict[str, Any] | None = None
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


class MLTrainingRun(Schema):
    id: str
    job_id: str
    dataset_id: str
    feature_version: str
    model_family: str
    hyperparameters: dict[str, Any]
    seed: int
    environment: dict[str, Any] | None = None
    status: str
    model_id: str | None = None
    error: str
    requested_by: str
    started_at: float
    finished_at: float | None = None


class MLModel(Schema):
    id: str
    name: str
    version: int
    state: str
    deployed: bool
    artifact_digest: str
    passport_digest: str
    feature_version: str
    dataset_id: str
    training_run_id: str
    created_at: float
    approval: dict[str, Any] | None = None
    passport: dict[str, Any]
    events: list[dict[str, Any]]
    deployments: list[dict[str, Any]]


class MLApprovalInput(Input):
    justification: str = Field(min_length=1, max_length=2000)


class MLDeployInput(Input):
    reason: str = Field(default="", max_length=2000)


class MLRollbackInput(Input):
    target_model_id: str | None = Field(default=None, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)


class MLReasonInput(Input):
    reason: str = Field(min_length=1, max_length=2000)


class MLDeployment(Schema):
    id: str
    model_name: str
    model_id: str
    kind: str
    active: bool
    previous_deployment_id: str | None = None
    deployed_by: str
    reason: str
    created_at: float
    deactivated_at: float | None = None


class MLMonitoring(Schema):
    model_name: str
    status: Literal["no_deployed_model", "no_observations", "observed"]
    active_deployment: MLDeployment | None = None
    all_models: dict[str, Any]
    active_model: dict[str, Any] | None = None


class MLDriftInput(Input):
    window: int = Field(default=500, ge=30, le=5000)


class MLDriftReport(Schema):
    id: str
    model_id: str
    job_id: str
    metric: str
    threshold: float
    baseline_count: int
    current_count: int
    window_start: float | None = None
    window_end: float | None = None
    result: Literal["drift", "no_drift", "insufficient_data"]
    details: dict[str, Any]
    policy_version: str
    created_at: float


class MLRetrainingRequest(Schema):
    id: str
    model_name: str
    model_id: str | None = None
    trigger: str
    status: str
    evidence: dict[str, Any]
    requested_by: str
    resolved_by: str | None = None
    resolution: str
    training_job_id: str | None = None
    created_at: float
    resolved_at: float | None = None


class MLAcceptRetrainingInput(Input):
    dataset_id: str = Field(min_length=1, max_length=128)


class MLInference(Schema):
    id: str
    run_id: str
    model_name: str
    model_id: str | None = None
    deployment_id: str | None = None
    artifact_digest: str | None = None
    feature_version: str
    features: list[float] | None = None
    status: Literal["scored", "abstained"]
    abstain_reason: str | None = None
    score: float | None = None
    latency_ms: float
    content_digest: str
    created_at: float


class ReviewerBriefing(Schema):
    id: str
    run_id: str
    capability: str
    status: Literal["generated", "deterministic", "abstained"]
    provider: str | None = None
    model: str | None = None
    fallback_level: int | None = None
    abstain_reason: str | None = None
    attempts: list[dict[str, Any]]
    output: dict[str, Any] | None = None
    content_digest: str
    latency_ms: float
    created_at: float


class CanonicalRecord(Schema):
    record_id: str
    category: str
    payload: dict[str, Any]
    content_digest: str
    source_record_id: str
    artifact_id: str
    locator: str
    file_digest: str
    original_record_digest: str
