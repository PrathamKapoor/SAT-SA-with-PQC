"""ML Framework Adapter Layer and Drift Detection."""
from qsmlops.ml.adapters import (
    TrainerInterface,
    ArtifactSerializerInterface,
    ModelMetadata,
    TrainingResult,
    SKLearnTrainer,
    SKLearnSerializer,
    get_trainer,
    get_serializer,
)

from qsmlops.ml.drift import (
    DriftReport,
    DriftConfig,
    PSIDriftDetector,
    KSDriftDetector,
    PredictionDriftDetector,
    PerformanceDriftDetector,
    DriftDetectionEngine,
)

__all__ = [
    "TrainerInterface",
    "ArtifactSerializerInterface",
    "ModelMetadata",
    "TrainingResult",
    "SKLearnTrainer",
    "SKLearnSerializer",
    "get_trainer",
    "get_serializer",
    "DriftReport",
    "DriftConfig",
    "PSIDriftDetector",
    "KSDriftDetector",
    "PredictionDriftDetector",
    "PerformanceDriftDetector",
    "DriftDetectionEngine",
]

if __name__ == "__main__":
    print("ML module loaded successfully")