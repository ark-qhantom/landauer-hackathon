"""landauer.ledger — the Reality Ledger: a durable, append-only JSONL receipt store.

Every decision Landauer makes (allowed, blocked, or escalated) is written as one receipt line. The
ledger is the audit surface enterprises need before trusting agents: who proposed what, under which
policy version, whether a human approved, what it would cost in dollars and joules, the decision, and
why. Receipts are written for BLOCKED actions too — the refusal is itself an auditable event.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# The canonical receipt schema (order preserved for readable JSONL / table rendering).
LEDGER_FIELDS = [
    "timestamp",
    "receipt_id",
    "agent_id",
    "policy_version",
    "action",
    "human_approved",
    "usd_estimate",
    "usd_cap",
    "joules_estimate",
    "joules_cap",
    "joules_measured",
    "runtime_seconds",
    "runtime_cap",
    "decision",
    "reason",
    "stripe_object_id",   # optional — present when a real Stripe object was created
    "nvidia_telemetry",   # optional — present when real nvidia-smi telemetry backed the joules
]


class Ledger:
    """Append-only JSONL ledger. receipt_ids are sequential and human-quotable (landauer_001, ...)."""

    def __init__(self, path: str | Path = "ledger/landauer_events.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _next_receipt_id(self) -> str:
        return f"landauer://receipt/{len(self.read_all()) + 1:03d}"

    def write(self, decision, *, runtime_seconds: Optional[float] = None,
              timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Append one receipt for a Decision and return the written record (including its receipt_id)."""
        record = {
            "timestamp": timestamp or datetime.now().isoformat(timespec="seconds"),
            "receipt_id": self._next_receipt_id(),
            "agent_id": decision.agent,
            "policy_version": decision.policy_version,
            "action": decision.action,
            "human_approved": decision.human_approved,
            "usd_estimate": decision.usd_estimate,
            "usd_cap": decision.usd_cap,
            "joules_estimate": decision.joules_estimate,
            "joules_cap": decision.joules_cap,
            "joules_measured": decision.joules_measured,
            "runtime_seconds": runtime_seconds if runtime_seconds is not None else decision.runtime_seconds,
            "runtime_cap": decision.runtime_cap,
            "decision": decision.decision,
            "reason": decision.reason,
            "stripe_object_id": decision.stripe_object_id,
            "nvidia_telemetry": decision.nvidia_telemetry,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def read_all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def clear(self) -> None:
        """Truncate the ledger (used by the demo runner to start a clean recording)."""
        if self.path.exists():
            self.path.unlink()
