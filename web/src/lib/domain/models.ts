import type { Tone } from "@/components/ui/badges";
import type { AbstainReason, DatasetStatus, MLDriftReport, ModelState } from "@/lib/api/types";

/** Display vocabulary for the MLOps lifecycle (docs/MLOPS.md). */

export const MODEL_STATE_TONE: Record<ModelState, Tone> = {
  registered: "neutral",
  verified: "info",
  quarantined: "critical",
  approved: "brand",
  retired: "neutral",
};

export const DATASET_TONE: Record<DatasetStatus, Tone> = {
  created: "neutral",
  validating: "info",
  valid: "brand",
  invalid: "critical",
  archived: "neutral",
};

export const DRIFT_TONE: Record<MLDriftReport["result"], Tone> = { drift: "attention", no_drift: "brand", insufficient_data: "neutral" };
export const DRIFT_LABEL: Record<MLDriftReport["result"], string> = { drift: "Drift", no_drift: "No drift", insufficient_data: "Insufficient data" };

export const ABSTAIN_LABEL: Record<AbstainReason, string> = {
  no_deployed_model: "No model is deployed",
  model_unavailable: "The deployed model could not be loaded or failed verification",
  feature_version_mismatch: "The deployed model expects a different feature version",
  missing_features: "The run lacks the inputs the model needs",
  out_of_distribution: "This run is outside the population the model was trained on",
  low_confidence: "The estimate was too close to 50% to be informative",
  inference_error: "The model failed; review continues without a score",
};
