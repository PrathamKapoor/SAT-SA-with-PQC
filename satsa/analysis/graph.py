"""LangGraph orchestration of durable SAT-SA analysis, without LLM calls.

The Phase 3 queue owns execution and leases. Graph state contains references
only; analytical output, recommendations and decisions live in domain tables.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from qsmlops.core.errors import PermissionDeniedError
from satsa.analysis.execution import Lease


class AnalysisGraphState(TypedDict, total=False):
    run_id: str
    organization_id: str
    submission_version_id: str
    current_stage: str
    review_decision_id: str
    recommendation_count: int
    trust_finalization: str


@contextmanager
def durable_checkpointer(engine):
    """Keep checkpoints in PostgreSQL or a durable offline SQLite sidecar."""
    os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"
    if engine.dialect == "postgresql":
        with PostgresSaver.from_conn_string(engine.dsn) as saver:
            saver.setup()
            yield saver
    else:
        path = engine.db_path.with_name(engine.db_path.name + ".langgraph.sqlite")
        with SqliteSaver.from_conn_string(str(path)) as saver:
            yield saver


class AnalysisGraphRuntime:
    def __init__(self, worker, lease: Lease, context: dict, checkpointer) -> None:
        self.worker = worker
        self.lease = lease
        self.context = context
        self.db = worker.db
        builder = StateGraph(AnalysisGraphState)
        builder.add_node("readiness", self.readiness)
        builder.add_node("analysis", self.analysis)
        builder.add_node("recommendations", self.recommendations)
        builder.add_node("human_review", self.human_review)
        builder.add_node("trust_boundary", self.trust_boundary)
        builder.add_edge(START, "readiness")
        builder.add_edge("readiness", "analysis")
        builder.add_edge("analysis", "recommendations")
        builder.add_edge("recommendations", "human_review")
        builder.add_edge("human_review", "trust_boundary")
        builder.add_edge("trust_boundary", END)
        self.graph = builder.compile(checkpointer=checkpointer)
        self.config: RunnableConfig = {
            "configurable": {"thread_id": f"satsa:{lease.run_id}"}
        }

    def _check(self, state: AnalysisGraphState) -> None:
        self.worker._assert_lease(self.lease)
        if (
            state["run_id"] != self.lease.run_id
            or state["organization_id"] != self.lease.organization_id
        ):
            raise PermissionDeniedError("graph state does not match leased run")
        if state["submission_version_id"] != self.context["submission_version_id"]:
            raise PermissionDeniedError(
                "graph version does not match leased submission"
            )
        if self.worker._cancel_requested(self.lease.run_id, self.lease.organization_id):
            from satsa.analysis.execution import CancelAtBoundary

            raise CancelAtBoundary()

    def readiness(self, state: AnalysisGraphState) -> dict:
        self._check(state)
        return {"current_stage": "analysis"}

    def analysis(self, state: AnalysisGraphState) -> dict:
        self._check(state)
        # Phase 3 persists each deterministic worker stage atomically and
        # skips completed stages on retry. Its existing risk result is unique.
        self.worker._execute(self.lease, self.context)
        self._check(state)
        if self.worker._finish(self.lease) == "failed":
            raise RuntimeError("all analytical stages failed; review is unavailable")
        return {"current_stage": "recommendations"}

    def recommendations(self, state: AnalysisGraphState) -> dict:
        self._check(state)
        count = self.worker._persist_recommendations(self.lease)
        return {"current_stage": "human_review", "recommendation_count": count}

    def human_review(self, state: AnalysisGraphState) -> dict:
        self._check(state)
        decision_id = interrupt({"run_id": self.lease.run_id, "stage": "human_review"})
        row = self.db.query_one(
            "SELECT id FROM satsa_run_review_decisions WHERE organization_id=? AND run_id=? AND id=?",
            (self.lease.organization_id, self.lease.run_id, decision_id),
        )
        if row is None:
            raise PermissionDeniedError(
                "supervisory decision was not persisted for this run"
            )
        return {"current_stage": "trust_boundary", "review_decision_id": decision_id}

    def trust_boundary(self, state: AnalysisGraphState) -> dict:
        self._check(state)
        row = self.db.query_one(
            "SELECT id FROM satsa_run_review_decisions WHERE organization_id=? AND run_id=? AND id=?",
            (
                self.lease.organization_id,
                self.lease.run_id,
                state["review_decision_id"],
            ),
        )
        if row is None:
            raise PermissionDeniedError(
                "supervisory decision missing at trust boundary"
            )
        self.worker._finalize_supervisory(self.lease)
        return {"current_stage": "finalization", "trust_finalization": "verified"}

    def run(self) -> str:
        snapshot = self.graph.get_state(self.config)
        payload: AnalysisGraphState | Command | None
        decision = self.db.query_one(
            "SELECT id FROM satsa_run_review_decisions WHERE organization_id=? AND run_id=?",
            (self.lease.organization_id, self.lease.run_id),
        )
        if snapshot.tasks and any(task.interrupts for task in snapshot.tasks):
            if self.worker._cancel_requested(
                self.lease.run_id, self.lease.organization_id
            ):
                from satsa.analysis.execution import CancelAtBoundary

                raise CancelAtBoundary()
            if decision is None:
                return "awaiting_review"
            payload = Command(resume=decision["id"])
        elif snapshot.values:
            payload = None
        else:
            payload = AnalysisGraphState(
                run_id=self.lease.run_id,
                organization_id=self.lease.organization_id,
                submission_version_id=self.context["submission_version_id"],
                current_stage="readiness",
            )
        result = self.graph.invoke(payload, self.config, version="v1")
        if "__interrupt__" in result:
            return "awaiting_review"
        if result.get("trust_finalization") not in {"ready", "verified"}:
            raise RuntimeError("graph did not reach the finalization boundary")
        return "finished"
