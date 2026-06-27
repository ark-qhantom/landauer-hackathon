"""Landauer — a runtime constitution for autonomous AI agents.

Landauer sits between an agent's intention and real-world action. It loads a human-defined policy
(the constitution) and gates every proposed action against hard rules for money, compute/energy,
runtime, credentials, and approvals BEFORE the action executes — then writes an auditable receipt.

    Humans set the rules. Agents do the work. Landauer enforces every dollar, joule, and decision
    before action.

Package layout (production-shaped core):
  - policy   : load + validate the human-readable constitution (config/demo_policy.yaml)
  - decision : the pure gate — ActionRequest -> Decision (allowed | blocked | escalate) + reason codes
  - ledger   : durable JSONL receipt ledger (the Reality Ledger)
  - adapters : Stripe (treasury), NVIDIA (telemetry), Hermes (proposer) — the real-world I/O, kept
               out of the pure kernel so the decision logic stays testable and deterministic.
"""

from .policy import Policy, load_policy
from .decision import ActionRequest, Decision, evaluate, Reason, ALLOWED, BLOCKED, ESCALATE, ALL_REASONS
from .ledger import Ledger

__all__ = [
    "Policy", "load_policy",
    "ActionRequest", "Decision", "evaluate", "Reason",
    "ALLOWED", "BLOCKED", "ESCALATE", "ALL_REASONS",
    "Ledger",
]
