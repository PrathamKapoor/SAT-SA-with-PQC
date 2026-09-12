"""Controlled supervisory benchmark — versioned manifest, seeded and
ground-truth-controlled measurement of the real SAT-SA pipeline."""
from evaluation.controlled_benchmark.manifest import (
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    build_manifest,
    validate_manifest,
)

__all__ = [
    "BENCHMARK_NAME",
    "BENCHMARK_VERSION",
    "build_manifest",
    "validate_manifest",
]