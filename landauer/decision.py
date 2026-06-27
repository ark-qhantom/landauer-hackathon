"""landauer.decision — the policy decision engine (the gate).

PURE and deterministic: given a loaded Policy and a proposed ActionRequest, return a structured
Decision (allowed | blocked | escalate) carrying exactly one canonical reason code. No I/O lives here —
adapters supply the estimates/measurements and perform side effects ONLY after an `allowed` decision.

THE LOAD-BEARING PROPERTY — "the cap is enforced below the human":
A human-approved action is still BLOCKED when it breaches a hard cap, unless the constitution explicitly
grants override for that resource (`approvals.human_can_override_usd / _joules`). Approval can clear a
soft gate (routing to a human) but cannot bribe a hard economic or physical limit.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

# --- decision verbs -------------------------------------------------------------------------------
ALLOWED = "allowed"
BLOCKED = "blocked"
ESCALATE = "escalate"


# --- canonical reason codes (the vocabulary judges read) ------------------------------------------
class Reason:
    WITHIN_POLICY = "within_policy"
    HUMAN_APPROVAL_MISSING = "human_approval_missing"
    USD_CAP_EXCEEDED = "usd_cap_exceeded"
    JOULE_CAP_EXCEEDED = "joule_cap_exceeded"
    RUNTIME_CAP_EXCEEDED = "runtime_cap_exceeded"
    CREDENTIAL_SCOPE_DENIED = "credential_scope_denied"
    PUBLIC_ACTION_REQUIRES_REVIEW = "public_action_requires_review"
    ACTION_NOT_ALLOWED = "action_not_allowed"


ALL_REASONS: List[str] = [
    Reason.WITHIN_POLICY,
    Reason.HUMAN_APPROVAL_MISSING,
    Reason.USD_CAP_EXCEEDED,
    Reason.JOULE_CAP_EXCEEDED,
    Reason.RUNTIME_CAP_EXCEEDED,
    Reason.CREDENTIAL_SCOPE_DENIED,
    Reason.PUBLIC_ACTION_REQUIRES_REVIEW,
    Reason.ACTION_NOT_ALLOWED,
]


@dataclass
class ActionRequest:
    """A single action a Hermes agent proposes. Estimates are supplied by adapters (Stripe/NVIDIA) or
    by the agent's own projection; `joules_measured` flags whether the joule figure is a REAL nvidia-smi
    measurement (∫P·dt) or a pre-execution projection."""
    action: str
    human_approved: bool = False
    usd_estimate: Optional[float] = None
    joules_estimate: Optional[float] = None
    runtime_seconds: Optional[float] = None
    credential_scope: Optional[str] = None
    joules_measured: bool = False
    nvidia_telemetry: Optional[Dict[str, Any]] = None
    stripe_object_id: Optional[str] = None
    note: str = ""


@dataclass
class Decision:
    agent: str
    policy_version: str
    action: str
    human_approved: bool
    usd_estimate: Optional[float]
    usd_cap: Optional[float]
    joules_estimate: Optional[float]
    joules_cap: Optional[float]
    runtime_seconds: Optional[float]
    runtime_cap: Optional[float]
    decision: str
    reason: str
    stripe_object_id: Optional[str] = None
    nvidia_telemetry: Optional[Dict[str, Any]] = None
    joules_measured: bool = False   # True if joules_estimate is a REAL ∫P·dt measurement, not a projection
    note: str = ""

    @property
    def is_allowed(self) -> bool:
        return self.decision == ALLOWED

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate(policy, req: ActionRequest) -> Decision:
    """Gate a proposed action against the constitution. Order is deliberate: a credential-scope (security)
    denial is surfaced first, then the hard caps (which bind below the human), then approval/review routing
    — a security denial outranks an economic/physical cap, which outranks a soft approval gate."""
    limits = policy.limits
    appr = policy.approvals
    action_policy = policy.actions.get(req.action)

    def mk(decision: str, reason: str) -> Decision:
        return Decision(
            agent=policy.agent_id,
            policy_version=policy.policy_version,
            action=req.action,
            human_approved=req.human_approved,
            usd_estimate=req.usd_estimate,
            usd_cap=limits.max_usd_per_task,
            joules_estimate=req.joules_estimate,
            joules_cap=limits.max_joules_per_task,
            runtime_seconds=req.runtime_seconds,
            runtime_cap=limits.max_runtime_seconds,
            decision=decision,
            reason=reason,
            stripe_object_id=req.stripe_object_id,
            nvidia_telemetry=req.nvidia_telemetry,
            joules_measured=req.joules_measured,
            note=req.note,
        )

    # 0. The action must be named in the constitution and permitted at all.
    if action_policy is None or not action_policy.allowed:
        return mk(BLOCKED, Reason.ACTION_NOT_ALLOWED)

    # 1. CREDENTIAL SCOPE — a hard SECURITY denial, surfaced ABOVE the economic/physical caps (a security
    #    violation is the more important signal than an over-budget one). BOTH the action's constitution-
    #    mandated scope AND any caller-asserted scope are checked — denying if EITHER is ungranted — so an
    #    agent can neither dodge the gate by omitting a scope nor MASK it by asserting a benign one.
    for needed_scope in (action_policy.required_credential_scope, req.credential_scope):
        if needed_scope and needed_scope not in policy.credentials.allowed_scopes:
            return mk(BLOCKED, Reason.CREDENTIAL_SCOPE_DENIED)

    # 2. HARD CAPS — enforced below the human. Approval lifts a cap only if the policy grants override
    #    for that specific resource (it does not, by default).
    if req.usd_estimate is not None and req.usd_estimate > limits.max_usd_per_task:
        if not (req.human_approved and appr.human_can_override_usd):
            return mk(BLOCKED, Reason.USD_CAP_EXCEEDED)
    if req.joules_estimate is not None and req.joules_estimate > limits.max_joules_per_task:
        if not (req.human_approved and appr.human_can_override_joules):
            return mk(BLOCKED, Reason.JOULE_CAP_EXCEEDED)
    if req.runtime_seconds is not None and req.runtime_seconds > limits.max_runtime_seconds:
        return mk(BLOCKED, Reason.RUNTIME_CAP_EXCEEDED)

    # 3. Review / approval routing -> ESCALATE (route to a human; not a hard refusal).
    if action_policy.requires_human_review and not req.human_approved:
        return mk(ESCALATE, Reason.PUBLIC_ACTION_REQUIRES_REVIEW)
    if appr.human_required and not req.human_approved:
        return mk(ESCALATE, Reason.HUMAN_APPROVAL_MISSING)

    # 4. Clear on every axis.
    return mk(ALLOWED, Reason.WITHIN_POLICY)
