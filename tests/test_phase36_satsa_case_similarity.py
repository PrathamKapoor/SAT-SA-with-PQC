"""Phase 36 — investigation similarity tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from satsa.analysis.case_similarity import (
    CaseSimilarity, case_actions, sequence_similarity, similar_cases,
)


def _step(action_type, sequence=0):
    return SimpleNamespace(action_type=action_type, sequence=sequence)


def test_sequence_similarity_identical():
    assert sequence_similarity(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_sequence_similarity_completely_different():
    assert sequence_similarity(["a"], ["b"]) == 0.0


def test_sequence_similarity_one_edit():
    # a -> b: 1 edit, length 3 → similarity 2/3
    assert abs(sequence_similarity(["a", "b", "c"], ["a", "x", "c"]) - 2/3) < 0.01


def test_sequence_similarity_both_empty():
    assert sequence_similarity([], []) == 1.0


def test_sequence_similarity_one_empty_one_not():
    assert sequence_similarity([], ["a"]) == 0.0
    assert sequence_similarity(["a"], []) == 0.0


def test_case_actions_extracts_ordered_set():
    """case_actions should return the unique action types in
    step-occurrence order, ignoring duplicates."""
    steps = [_step("a"), _step("b"), _step("a"), _step("c")]
    assert case_actions(steps) == ("a", "b", "c")


def test_similar_cases_returns_pairs_above_threshold():
    steps = {
        "c1": [_step("a"), _step("b"), _step("c")],
        "c2": [_step("a"), _step("b"), _step("c")],
        "c3": [_step("x"), _step("y")],
    }
    pairs = similar_cases(steps, threshold=0.8)
    assert len(pairs) == 1
    assert pairs[0].case_id_a == "c1"
    assert pairs[0].case_id_b == "c2"
    assert pairs[0].similarity == 1.0
    assert pairs[0].shared_actions == {"a": 1, "b": 1, "c": 1}


def test_similar_cases_does_not_pair_below_threshold():
    steps = {
        "c1": [_step("a")],
        "c2": [_step("b")],
        "c3": [_step("c")],
    }
    pairs = similar_cases(steps, threshold=0.8)
    assert pairs == []


def test_similar_cases_sorted_by_similarity_descending():
    steps = {
        "c1": [_step("a"), _step("b"), _step("c")],
        "c2": [_step("a"), _step("b"), _step("c")],
        "c3": [_step("a"), _step("x"), _step("c")],
        "c4": [_step("a")],
    }
    pairs = similar_cases(steps, threshold=0.5)
    assert len(pairs) > 0
    # Each subsequent pair has similarity <= the previous
    for i in range(1, len(pairs)):
        assert pairs[i - 1].similarity >= pairs[i].similarity


def test_case_similarity_to_dict():
    s = CaseSimilarity(case_id_a="c1", case_id_b="c2",
                       actions_a=("a", "b"), actions_b=("a", "b"),
                       similarity=1.0, shared_actions={"a": 1, "b": 1})
    d = s.to_dict()
    assert d["case_id_a"] == "c1"
    assert d["similarity"] == 1.0
    assert d["shared_actions"] == {"a": 1, "b": 1}


def test_similar_cases_handles_single_case():
    steps = {"c1": [_step("a")]}
    pairs = similar_cases(steps, threshold=0.5)
    assert pairs == []
