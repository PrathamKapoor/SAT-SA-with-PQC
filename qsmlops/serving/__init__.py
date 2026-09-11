"""Model serving layer.

Enforced deployment flow:

    Registry
      -> Passport verification (ML-DSA signature against trust anchors)
      -> Integrity check (artifact digest + BOM declaration + store re-hash)
      -> Load model (framework-aware deserialization)
      -> Serve (prediction with per-request evidence logging)

A model that fails any pre-load stage is never deserialized: no untrusted
bytes reach an execution path.
"""
from qsmlops.serving.service import ModelDeploymentService, ServingError

__all__ = ["ModelDeploymentService", "ServingError"]
