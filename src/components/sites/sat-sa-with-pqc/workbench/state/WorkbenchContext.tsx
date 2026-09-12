"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { QueueItem, initialQueueItems, DispositionType } from "../data/reviewQueue";
import { AuditLedgerEntry, auditLedgerEntries, governanceConfig } from "../data/governance";
import { Entity, entities } from "../data/entities";

interface WorkbenchContextType {
  // State
  queueItems: QueueItem[];
  auditEntries: AuditLedgerEntry[];
  entitiesList: Entity[];
  selectedCohort: string;
  setSelectedCohort: (cohort: string) => void;
  selectedPeriod: string;
  setSelectedPeriod: (period: string) => void;
  redactionMode: boolean;
  setRedactionMode: (val: boolean | ((prev: boolean) => boolean)) => void;
  lastActionSummary: string | null;

  // Actions (Revertable & Auditable)
  recordDisposition: (
    queueId: string,
    disposition: DispositionType,
    rationale: string,
    examiner?: string
  ) => void;
  revertDisposition: (queueId: string, reversalReason: string, examiner?: string) => void;
  undoLastAction: () => void;
  resetToBaseline: () => void;
  exportReviewPacket: (selectedIds?: string[]) => void;
}

const WorkbenchContext = createContext<WorkbenchContextType | null>(null);

const LOCAL_STORAGE_KEY_QUEUE = "satsa_workbench_queue_v1";
const LOCAL_STORAGE_KEY_AUDIT = "satsa_workbench_audit_v1";

export const WorkbenchProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [queueItems, setQueueItems] = useState<QueueItem[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const savedQueue = localStorage.getItem(LOCAL_STORAGE_KEY_QUEUE);
        if (savedQueue) return JSON.parse(savedQueue);
      } catch {
        // Ignore local storage error
      }
    }
    return initialQueueItems;
  });

  const [auditEntries, setAuditEntries] = useState<AuditLedgerEntry[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const savedAudit = localStorage.getItem(LOCAL_STORAGE_KEY_AUDIT);
        if (savedAudit) return JSON.parse(savedAudit);
      } catch {
        // Ignore local storage error
      }
    }
    return auditLedgerEntries;
  });

  const [entitiesList] = useState<Entity[]>(entities);
  const [selectedCohort, setSelectedCohort] = useState<string>("All Cohorts");
  const [selectedPeriod, setSelectedPeriod] = useState<string>("Aug–Sep 2026");
  const [redactionMode, setRedactionMode] = useState<boolean>(true);
  const [lastActionSummary, setLastActionSummary] = useState<string | null>(null);

  // Save to local storage on changes
  const persistState = (newQueue: QueueItem[], newAudit: AuditLedgerEntry[]) => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY_QUEUE, JSON.stringify(newQueue));
      localStorage.setItem(LOCAL_STORAGE_KEY_AUDIT, JSON.stringify(newAudit));
    } catch {
      // Storage quota or restriction
    }
  };

  const recordDisposition = useCallback(
    (
      queueId: string,
      disposition: DispositionType,
      rationale: string,
      examiner: string = "Examiner A. Sharma (Lead)"
    ) => {
      setQueueItems((prevQueue) => {
        const targetIndex = prevQueue.findIndex((item) => item.id === queueId);
        if (targetIndex === -1) return prevQueue;

        const target = prevQueue[targetIndex];
        const now = new Date().toISOString();
        const fakeDigest = `sha3_${Math.random().toString(36).substring(2, 12)}_${now.replace(/[^0-9]/g, "")}`;

        const newHistoryEntry = {
          id: `disp-hist-${Date.now()}`,
          disposition,
          rationale: rationale.trim(),
          timestamp: now,
          examiner,
          digest: fakeDigest,
          actionType: "subsequent_correction" as const,
        };

        const updatedItem: QueueItem = {
          ...target,
          currentDisposition: disposition,
          dispositionRationale: rationale.trim(),
          dispositionTimestamp: now,
          dispositionHistory: [...target.dispositionHistory, newHistoryEntry],
        };

        const newQueue = [...prevQueue];
        newQueue[targetIndex] = updatedItem;

        // Add to audit ledger
        const newAuditEntry: AuditLedgerEntry = {
          id: `blk-${auditEntries.length + 104}`,
          blockHeight: auditEntries.length + 104,
          occurredAt: now,
          principalIdentity: examiner.split(" ")[0].toUpperCase(),
          role: "NCIIPC Supervisory Examiner",
          action: "DISPOSITION_RECORD",
          subjectType: "finding",
          subjectIdentifier: `${target.id} (${target.entityName} ${target.alertOrCaseId})`,
          previousBlockDigestSha3: auditEntries[0]?.currentBlockDigestSha3 || "000000000000...",
          currentBlockDigestSha3: fakeDigest,
          pqcSignatureAlgorithm: "ML-DSA-65",
          pqcSignatureVerified: true,
          notes: `Disposition recorded: ${disposition.toUpperCase().replace(/_/g, " ")}. Rationale: "${rationale.slice(0, 80)}..."`,
        };

        const newAudit = [newAuditEntry, ...auditEntries];
        setAuditEntries(newAudit);
        persistState(newQueue, newAudit);
        setLastActionSummary(`Recorded disposition "${disposition.replace(/_/g, " ")}" on ${target.alertOrCaseId}`);

        return newQueue;
      });
    },
    [auditEntries]
  );

  const revertDisposition = useCallback(
    (queueId: string, reversalReason: string, examiner: string = "Examiner A. Sharma (Lead)") => {
      setQueueItems((prevQueue) => {
        const targetIndex = prevQueue.findIndex((item) => item.id === queueId);
        if (targetIndex === -1) return prevQueue;

        const target = prevQueue[targetIndex];
        const now = new Date().toISOString();
        const fakeDigest = `rev_sha3_${Math.random().toString(36).substring(2, 10)}`;

        // Determine prior state or revert to "open"
        const priorHistory = target.dispositionHistory;
        const previousState: DispositionType =
          priorHistory.length > 1
            ? priorHistory[priorHistory.length - 2].disposition
            : "open";

        const reversalHistoryEntry = {
          id: `disp-revert-${Date.now()}`,
          disposition: previousState,
          rationale: `REVERSAL: ${reversalReason.trim()}`,
          timestamp: now,
          examiner,
          digest: fakeDigest,
          actionType: "reversal" as const,
        };

        const updatedItem: QueueItem = {
          ...target,
          currentDisposition: previousState,
          dispositionRationale: `[Reverted] ${reversalReason.trim()}`,
          dispositionTimestamp: now,
          dispositionHistory: [...target.dispositionHistory, reversalHistoryEntry],
        };

        const newQueue = [...prevQueue];
        newQueue[targetIndex] = updatedItem;

        const newAuditEntry: AuditLedgerEntry = {
          id: `blk-${auditEntries.length + 104}`,
          blockHeight: auditEntries.length + 104,
          occurredAt: now,
          principalIdentity: examiner.split(" ")[0].toUpperCase(),
          role: "NCIIPC Supervisory Examiner",
          action: "DISPOSITION_REVERSAL",
          subjectType: "finding",
          subjectIdentifier: `${target.id} (${target.entityName})`,
          previousBlockDigestSha3: auditEntries[0]?.currentBlockDigestSha3 || "000000000000...",
          currentBlockDigestSha3: fakeDigest,
          pqcSignatureAlgorithm: "ML-DSA-65",
          pqcSignatureVerified: true,
          notes: `REVERSAL EXECUTED: Reverted to ${previousState.toUpperCase()}. Reason: "${reversalReason}"`,
        };

        const newAudit = [newAuditEntry, ...auditEntries];
        setAuditEntries(newAudit);
        persistState(newQueue, newAudit);
        setLastActionSummary(`Reverted ${target.alertOrCaseId} to "${previousState.replace(/_/g, " ")}"`);

        return newQueue;
      });
    },
    [auditEntries]
  );

  const undoLastAction = useCallback(() => {
    // Find last modified item
    const modified = queueItems.find((item) => item.dispositionHistory.length > 1);
    if (!modified) {
      alert("No review actions available to undo.");
      return;
    }
    revertDisposition(modified.id, "Examiner executed immediate undo");
  }, [queueItems, revertDisposition]);

  const resetToBaseline = useCallback(() => {
    if (confirm("Reset workbench review state back to the initial verified assessment baseline? All custom dispositions will be cleared and logged.")) {
      const now = new Date().toISOString();
      const resetAudit: AuditLedgerEntry = {
        id: `blk-${auditEntries.length + 104}`,
        blockHeight: auditEntries.length + 104,
        occurredAt: now,
        principalIdentity: "SUPERVISORY_ADMIN",
        role: "NCIIPC Examiner Lead",
        action: "POLICY_OVERRIDE",
        subjectType: "assessment",
        subjectIdentifier: "CYCLE-2026-08",
        previousBlockDigestSha3: auditEntries[0]?.currentBlockDigestSha3 || "00000...",
        currentBlockDigestSha3: "reset_baseline_sha3_digest",
        pqcSignatureAlgorithm: "ML-DSA-65",
        pqcSignatureVerified: true,
        notes: "Workbench state manually reset to baseline by lead examiner.",
      };

      const newAudit = [resetAudit, ...auditEntries];
      setQueueItems(initialQueueItems);
      setAuditEntries(newAudit);
      persistState(initialQueueItems, newAudit);
      setLastActionSummary("State reset to initial verified cycle baseline.");
    }
  }, [auditEntries]);

  const exportReviewPacket = useCallback(
    (selectedIds?: string[]) => {
      const targetItems = selectedIds && selectedIds.length > 0
        ? queueItems.filter((q) => selectedIds.includes(q.id))
        : queueItems;

      const packet = {
        packetMetadata: {
          title: "NCIIPC SAT-SA Supervisory Review Packet",
          assessmentPeriod: selectedPeriod,
          exportedAt: new Date().toISOString(),
          pqcSignatureStandard: governanceConfig.cryptographicStandard,
          pqcReceiptVerification: "VERIFIED_VALID",
          examinerAttestation: "Auditable supervisory review packet compiled for regulatory inspection.",
        },
        reviewedSamples: targetItems.map((item) => ({
          rank: item.rank,
          priority: item.priority,
          entity: item.entityName,
          asset: item.assetName,
          alertId: item.alertOrCaseId,
          findingFamily: item.findingFamilyLabel,
          currentDisposition: item.currentDisposition,
          dispositionRationale: item.dispositionRationale || "Pending examiner input",
          examinerAssignment: item.assignedExaminer,
          auditHistoryCount: item.dispositionHistory.length,
          dispositionLedger: item.dispositionHistory,
        })),
        auditTrailDigestChain: auditEntries.slice(0, 10),
      };

      const blob = new Blob([JSON.stringify(packet, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `NCIIPC-SUPERVISORY-PACKET-${selectedPeriod.replace(/[^a-zA-Z0-9]/g, "_")}.json`;
      a.click();
      URL.revokeObjectURL(url);
    },
    [queueItems, selectedPeriod, auditEntries]
  );

  return (
    <WorkbenchContext.Provider
      value={{
        queueItems,
        auditEntries,
        entitiesList,
        selectedCohort,
        setSelectedCohort,
        selectedPeriod,
        setSelectedPeriod,
        redactionMode,
        setRedactionMode,
        lastActionSummary,
        recordDisposition,
        revertDisposition,
        undoLastAction,
        resetToBaseline,
        exportReviewPacket,
      }}
    >
      {children}
    </WorkbenchContext.Provider>
  );
};

export function useWorkbench() {
  const ctx = useContext(WorkbenchContext);
  if (!ctx) {
    throw new Error("useWorkbench must be used within a WorkbenchProvider");
  }
  return ctx;
}
