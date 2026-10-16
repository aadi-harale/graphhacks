"""Observed receipts, supplier statements and approved settlements remain separate."""
from dataclasses import dataclass, field
from typing import Literal

@dataclass(frozen=True)
class Obligation:
    id: str
    sku: str
    kind: str
    original_qty: int
    outstanding_qty: int
    version: int = 0
    proof_ref: str = ""

@dataclass(frozen=True)
class Statement:
    id: str
    target_id: str
    proof_ref: str
    active: bool = True

@dataclass(frozen=True)
class Receipt:
    id: str
    supplier_id: str
    sku: str
    original_qty: int
    available_qty: int
    retailer_confirmed: bool
    proof_ref: str
    version: int = 0
    unit_known: bool = True

@dataclass(frozen=True)
class Context:
    receipt: Receipt
    obligations: tuple[Obligation, ...]
    statements: tuple[Statement, ...]
    promises: dict[str, tuple[str, ...]] = field(default_factory=dict)
    paths: dict[str, tuple[str, ...]] = field(default_factory=dict)
    tool_trace: tuple[str, ...] = ()

@dataclass(frozen=True)
class Decision:
    status: Literal["ASK_SUPPLIER", "REVIEW_SETTLEMENT", "ASK_RETAILER",
                    "DISPUTE", "UNKNOWN", "NO_OPEN_CLAIMS", "ALREADY_ALLOCATED"]
    receipt_id: str
    title: str
    explanation: str
    requested_evidence: str
    candidate_ids: tuple[str, ...]
    suggested_obligation: str | None = None
    suggested_qty: int = 0
    evidence_paths: dict[str, tuple[str, ...]] = field(default_factory=dict)
    graph_tool_trace: tuple[str, ...] = ()
    risk: str = "review_required"

    def to_dict(self):
        return {
            "status": self.status, "receipt_id": self.receipt_id,
            "title": self.title, "explanation": self.explanation,
            "requested_evidence": self.requested_evidence,
            "candidate_ids": list(self.candidate_ids),
            "suggested_obligation": self.suggested_obligation,
            "suggested_qty": self.suggested_qty,
            "evidence_paths": {k: list(v) for k, v in self.evidence_paths.items()},
            "graph_tool_trace": list(self.graph_tool_trace), "risk": self.risk,
        }
