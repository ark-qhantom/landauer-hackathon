"""landauer.policy — load and validate the human-readable runtime constitution.

The policy is the single source of truth for what the agent may do and the hard limits it operates
under. It is plain YAML so a human can read, review, and version it. This module turns that YAML into
typed, validated dataclasses; it performs NO enforcement (that is `landauer.decision`).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass(frozen=True)
class Limits:
    max_usd_per_task: float
    max_joules_per_task: float
    max_runtime_seconds: float


@dataclass(frozen=True)
class Approvals:
    human_required: bool = True
    human_can_override_usd: bool = False
    human_can_override_joules: bool = False


@dataclass(frozen=True)
class Treasury:
    currency: str = "usd"
    budget_usd: float = 1.00


@dataclass(frozen=True)
class Credentials:
    allowed_scopes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ActionPolicy:
    allowed: bool = True
    requires_human_review: bool = False
    required_credential_scope: Optional[str] = None   # scope the action needs; gate denies if not granted


@dataclass(frozen=True)
class Policy:
    agent_id: str
    policy_version: str
    limits: Limits
    approvals: Approvals
    actions: Dict[str, ActionPolicy]
    treasury: Treasury = field(default_factory=Treasury)
    credentials: Credentials = field(default_factory=Credentials)

    def action(self, name: str) -> ActionPolicy | None:
        return self.actions.get(name)


def load_policy(path: str | Path) -> Policy:
    """Parse and validate config/demo_policy.yaml into a typed Policy. Raises on missing required fields."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"policy file {path} did not parse to a mapping")

    for required in ("agent_id", "policy_version", "limits", "approvals", "actions"):
        if required not in data:
            raise ValueError(f"policy file {path} missing required key: {required!r}")

    lim = data["limits"]
    limits = Limits(
        max_usd_per_task=float(lim["max_usd_per_task"]),
        max_joules_per_task=float(lim["max_joules_per_task"]),
        max_runtime_seconds=float(lim["max_runtime_seconds"]),
    )
    # robust to extra/typo'd keys (fail-closed on a benign typo is worse than ignoring it)
    _appr_fields = {f.name for f in fields(Approvals)}
    approvals = Approvals(**{k: bool(v) for k, v in (data.get("approvals") or {}).items() if k in _appr_fields})

    tre = data.get("treasury") or {}
    treasury = Treasury(currency=tre.get("currency", "usd"), budget_usd=float(tre.get("budget_usd", 1.00)))

    cred = data.get("credentials") or {}
    credentials = Credentials(allowed_scopes=list(cred.get("allowed_scopes", [])))

    actions: Dict[str, ActionPolicy] = {}
    for name, spec in (data["actions"] or {}).items():
        spec = spec or {}
        actions[name] = ActionPolicy(
            allowed=bool(spec.get("allowed", True)),
            requires_human_review=bool(spec.get("requires_human_review", False)),
            required_credential_scope=spec.get("required_credential_scope"),
        )

    return Policy(
        agent_id=str(data["agent_id"]),
        policy_version=str(data["policy_version"]),
        limits=limits,
        approvals=approvals,
        actions=actions,
        treasury=treasury,
        credentials=credentials,
    )
