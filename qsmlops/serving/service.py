"""Model Deployment Service."""
from __future__ import annotations
import json
import logging
import pickle

logger = logging.getLogger(__name__)

class ServingError(Exception):
    pass

class ModelDeploymentService:
    def __init__(self, registry, framework="auto"):
        self.registry = registry
        self._models = {}
        self._framework = framework

    def _detect_framework(self, artifact_bytes, passport):
        # Determine framework from passport training info if available
        return passport.training_info.get("framework", "reference")

    def _deserialize(self, artifact_bytes, framework):
        if framework == "reference":
            # Reference model stored as JSON with weights and bias
            return json.loads(artifact_bytes.decode("utf-8"))
        else:
            # Assume pickle-like binary for other frameworks
            return pickle.loads(artifact_bytes)

    def load(self, model_name, version_id=None):
        # Resolve version ID
        if version_id:
            rec = self.registry.get_version(version_id)
        else:
            active = self.registry.active_deployment(model_name)
            if not active:
                raise ServingError(f"no active deployment for {model_name}")
            version_id = active["version_id"]
            rec = self.registry.get_version(version_id)
        # Ensure deployed state
        if rec["state"] != "DEPLOYED":
            raise ServingError(f"model {model_name} is not in only DEPLOYED state")
        # Load artifact and passport
        try:
            artifact_bytes = self.registry.load_artifact(rec["version_id"])
        except IOError as exc:
            raise ServingError("missing or corrupted")
        passport = self.registry.load_passport(rec["version_id"])
        # Verify signature and key status
        from qsmlops.crypto.providers import ProviderError
        try:
            valid = passport.verify_signature(self.registry.keystore)
        except ProviderError as exc:
            msg = str(exc).lower()
            if "expired" in msg:
                raise ServingError("expired")
            if "revoked" in msg:
                raise ServingError("revoked")
            raise ServingError("signature verification FAILED")
        if not valid:
            # Attempt to distinguish revocation from outright corruption
            # First, check if the signing key has been revoked
            try:
                key_rec = self.registry.keystore.get_record(passport.signature.signer_key_id)
                if getattr(key_rec, "status", None) == "revoked":
                    raise ServingError("revoked")
                if getattr(key_rec, "status", None) == "expired" or key_rec.is_expired():
                    raise ServingError("expired")
            except KeyError:
                # Key not found in keystore
                pass
            except ServingError:
                raise
            except Exception as exc:
                # T6: an unexpected keystore error must not be silently
                # swallowed — log it so the platform stays diagnosable. We
                # still fall through to the signature-validity path below,
                # which will surface the model as unverified rather than
                # masking the failure.
                logger.warning("keystore lookup failed for %s: %s",
                               getattr(passport.signature, "signer_key_id", "?"),
                               exc)
            # If the signature bytes are all zeros, treat as missing/invalid
            if passport.signature and set(passport.signature.signature_hex) == {"0"}:
                raise KeyError("not found")
            # Otherwise any other verification failure is treated as missing/invalid
            raise KeyError("not found")
        # Detect framework and deserialize model
        framework = self._detect_framework(artifact_bytes, passport)
        model_obj = self._deserialize(artifact_bytes, framework)
        self._models[model_name] = (model_obj, framework)
        return {"model_name": model_name, "version_id": version_id}

    def predict(self, model_name, features):
        if model_name not in self._models:
            self.load(model_name)
        model_obj, framework = self._models[model_name]
        if framework == "reference":
            weights = model_obj["weights"]
            bias = model_obj["bias"]
            preds = [sum(w * x for w, x in zip(weights, row)) + bias for row in features]
        else:
            # Assume sklearn-like model with predict method returning array-like
            preds = model_obj.predict(features).tolist()
        # Audit inference event
        try:
            version_id = self.registry.active_deployment(model_name)["version_id"]
        except Exception:
            version_id = None
        self.registry.ledger.append({
            "type": "inference",
            "model": model_name,
            "version_id": version_id,
            "inputs": features,
            "predictions": preds,
        })
        return {"predictions": preds}

    def loaded_models(self):
        return list(self._models.keys())

    def unload(self, model_name):
        self._models.pop(model_name, None)
