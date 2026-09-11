"""SAT-SA domain records (Part H/I). See docs/phase2/domain-foundation.md
and docs/phase2/data-contracts.md for what each record is for and what
remains unimplemented (ingestion parsing, persistence, detectors)."""
from __future__ import annotations

from satsa.domain.entities import Assessment, Asset, Entity, Submission
from satsa.domain.evidence import (
    ConfidenceVector,
    Finding,
    Observation,
    ProvenanceRecord,
    ReviewDecision,
    SourceRecord,
)
from satsa.domain.runs import AnalysisRun
from satsa.domain.workflow import Alert, Case, Disposition, Escalation, InvestigationStep

__all__ = [
    "Entity", "Assessment", "Submission", "Asset",
    "Alert", "Case", "InvestigationStep", "Escalation", "Disposition",
    "SourceRecord", "Observation", "Finding", "ConfidenceVector",
    "ReviewDecision", "ProvenanceRecord", "AnalysisRun",
]
