"""Phase P27 — public_benchmarks provenance tagging.

The one rule the whole public_benchmarks package exists to enforce:
every record it produces is machine-labeled with exactly where it
came from, and a record can never claim to be real SOC data.
"""
from __future__ import annotations

import pytest

from public_benchmarks.provenance import (
    DERIVED_FROM_SOURCE,
    DERIVED_SYNTHETIC_WORKFLOW,
    GENERATION_POLICY_VERSION,
    ProvenanceTag,
    is_real_soc_data,
    source_derived,
    synthetic_workflow,
)


def test_source_derived_tag_shape():
    tag = source_derived("CIC-IDS2017")
    assert tag.provenance_type == DERIVED_FROM_SOURCE
    assert tag.source_dataset == "CIC-IDS2017"
    assert tag.scenario_id == ""


def test_synthetic_workflow_tag_shape():
    tag = synthetic_workflow("Splunk BOTS v3", scenario_id="critical-unescalated-001")
    assert tag.provenance_type == DERIVED_SYNTHETIC_WORKFLOW
    assert tag.source_dataset == "Splunk BOTS v3"
    assert tag.scenario_id == "critical-unescalated-001"
    assert tag.generation_policy_version == GENERATION_POLICY_VERSION


def test_synthetic_workflow_requires_a_policy_version():
    """A generated workflow record with no policy version is a bug —
    it means the generator's own version tracking was bypassed."""
    with pytest.raises(ValueError):
        ProvenanceTag(
            provenance_type=DERIVED_SYNTHETIC_WORKFLOW,
            source_dataset="Splunk BOTS v3", scenario_id="x",
            generation_policy_version="")


def test_empty_source_dataset_is_rejected():
    with pytest.raises(ValueError):
        ProvenanceTag(provenance_type=DERIVED_FROM_SOURCE, source_dataset="")


def test_unknown_provenance_type_is_rejected():
    with pytest.raises(ValueError):
        ProvenanceTag(provenance_type="real_soc_data", source_dataset="x")


def test_to_dict_matches_the_user_specified_shape():
    tag = synthetic_workflow("Splunk BOTS v3", scenario_id="critical-unescalated-001",
                             policy_version="workflow-policy-v1")
    d = tag.to_dict()
    assert d == {
        "provenance_type": "derived_synthetic_workflow",
        "source_dataset": "Splunk BOTS v3",
        "scenario_id": "critical-unescalated-001",
        "generation_policy_version": "workflow-policy-v1",
    }


def test_is_real_soc_data_is_always_false():
    assert is_real_soc_data(source_derived("CIC-IDS2017")) is False
    assert is_real_soc_data(synthetic_workflow("BOTS", scenario_id="s1")) is False


def test_tag_is_frozen():
    tag = source_derived("CIC-IDS2017")
    with pytest.raises(Exception):
        tag.source_dataset = "tampered"
