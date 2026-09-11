"""Investigation-similarity analytics: structured, explainable.

Compares the investigation *structure* of two cases (their ordered
action-type sequences) and reports a deterministic, bounded
similarity score. This is deliberately NOT an embedding model
and NOT a learned similarity — it is exact-match-on-sequence with
a tolerance for small differences.

A pair of cases is "structurally similar" if their action-type
sequences match exactly, or differ only by insertions / deletions
of a few steps. The current implementation uses a simple
Levenshtein-style edit distance normalised by the longer sequence
length, which is bounded in [0.0, 1.0] where 1.0 = identical.

This module is intentionally simple, deterministic, and
air-gapped. It does NOT use any external embedding API or
downloaded model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


def _levenshtein(a: Sequence, b: Sequence) -> int:
    """Standard Wagner-Fischer edit distance."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(a) == 0:
        return len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(
                curr[j - 1] + 1,        # insertion
                prev[j] + 1,            # deletion
                prev[j - 1] + cost,     # substitution
            )
        prev = curr
    return prev[-1]


def sequence_similarity(a: Sequence, b: Sequence) -> float:
    """Bounded similarity in [0.0, 1.0]. 1.0 = identical sequences."""
    if not a and not b:
        return 1.0
    n = max(len(a), len(b))
    if n == 0:
        return 1.0
    return 1.0 - _levenshtein(a, b) / n


@dataclass
class CaseSimilarity:
    case_id_a: str
    case_id_b: str
    actions_a: tuple
    actions_b: tuple
    similarity: float
    shared_actions: dict

    def to_dict(self) -> dict:
        return {
            "case_id_a": self.case_id_a,
            "case_id_b": self.case_id_b,
            "actions_a": list(self.actions_a),
            "actions_b": list(self.actions_b),
            "similarity": round(self.similarity, 3),
            "shared_actions": dict(self.shared_actions),
        }


def case_actions(steps: list) -> tuple:
    """Extract the ordered action-type sequence from a case's
    investigation steps."""
    return tuple(sorted({s.action_type for s in steps},
                       key=lambda t: next((i for i, x in enumerate(steps) if x.action_type == t), 0)))


def similar_cases(case_steps: dict[str, list],
                 threshold: float = 0.8) -> list[CaseSimilarity]:
    """Find all pairs of cases whose investigation-structure
    similarity is >= ``threshold``. Input is a mapping of
    ``case_id -> [InvestigationStep, ...]``.

    Returns a list of ``CaseSimilarity`` records, one per pair.
    The result is deterministic and explainable: every similarity
    score is a simple edit-distance ratio."""
    results: list[CaseSimilarity] = []
    case_ids = list(case_steps.keys())
    for i, ca in enumerate(case_ids):
        for cb in case_ids[i + 1:]:
            seq_a = case_actions(case_steps[ca])
            seq_b = case_actions(case_steps[cb])
            sim = sequence_similarity(seq_a, seq_b)
            if sim >= threshold:
                shared: dict[str, int] = {}
                for action in set(seq_a) & set(seq_b):
                    shared[action] = min(
                        seq_a.count(action), seq_b.count(action))
                results.append(CaseSimilarity(
                    case_id_a=ca, case_id_b=cb,
                    actions_a=seq_a, actions_b=seq_b,
                    similarity=sim, shared_actions=shared,
                ))
    results.sort(key=lambda r: r.similarity, reverse=True)
    return results
