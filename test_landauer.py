#!/usr/bin/env python3
"""test_landauer.py — fast, deterministic verifier for the Landauer core (no GPU/Stripe/Hermes needed).

Proves: the constitution loads; every canonical reason code is reachable; the cap is enforced BELOW the
human; explicit override works only when the constitution grants it; the credential gate is non-bypassable;
per-agent `actor` flows onto the receipt; the ledger writes/reads receipts.

    python test_landauer.py        (exit 0 = all pass)
"""

import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from landauer import (ALLOWED, ALL_REASONS, BLOCKED, ESCALATE, ActionRequest, Ledger, Reason,
                      evaluate, load_policy)
from landauer.ledger import LEDGER_FIELDS
from landauer.policy import Approvals, Policy

_ok = True
_seen = set()


def check(label: str, cond: bool):
    global _ok
    _ok = _ok and bool(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")


def decide(policy, **kw):
    d = evaluate(policy, ActionRequest(**kw))
    _seen.add(d.reason)
    return d


POLICY = load_policy(ROOT / "config" / "demo_policy.yaml")

print("test_landauer.py — Landauer core verifier\n")

print("(1) constitution loads with expected caps")
check("agent / version", POLICY.agent_id == "hermes-demo-agent" and POLICY.policy_version == "landauer-demo-v1")
check("caps $500 / 1000 J / 30 s",
      POLICY.limits.max_usd_per_task == 500.0 and POLICY.limits.max_joules_per_task == 1000
      and POLICY.limits.max_runtime_seconds == 30)
check("human required, no usd/joule override",
      POLICY.approvals.human_required and not POLICY.approvals.human_can_override_usd
      and not POLICY.approvals.human_can_override_joules)

print("\n(2) allowed path -> within_policy")
d = decide(POLICY, action="call_api_model", human_approved=True, usd_estimate=42.0, joules_estimate=100, runtime_seconds=5)
check("ALLOWED within_policy", d.decision == ALLOWED and d.reason == Reason.WITHIN_POLICY)

print("\n(3) USD cap blocks below the human")
d = decide(POLICY, action="call_api_model", human_approved=True, usd_estimate=4800.0, joules_estimate=0, runtime_seconds=5)
check("BLOCKED usd_cap_exceeded despite human_approved ($4,800 > $500)",
      d.decision == BLOCKED and d.reason == Reason.USD_CAP_EXCEEDED)

print("\n(4) JOULE cap blocks below the human  ← the headline")
d = decide(POLICY, action="large_gpu_job", human_approved=True, usd_estimate=0.0, joules_estimate=18400, runtime_seconds=20)
check("BLOCKED joule_cap_exceeded despite human_approved + USD pass (18,400 J > 1,000 J)",
      d.decision == BLOCKED and d.reason == Reason.JOULE_CAP_EXCEEDED)

print("\n(5) runtime cap blocks")
d = decide(POLICY, action="run_local_model", human_approved=True, joules_estimate=100, runtime_seconds=60)
check("BLOCKED runtime_cap_exceeded (60 s > 30 s)", d.decision == BLOCKED and d.reason == Reason.RUNTIME_CAP_EXCEEDED)

print("\n(6) credential scope denied — driven by the CONSTITUTION, not caller-supplied data")
d = decide(POLICY, action="export_customer_data", human_approved=True, usd_estimate=0.0,
           joules_estimate=10, runtime_seconds=2)   # NO credential_scope passed by the caller
check("BLOCKED credential_scope_denied (from policy required_credential_scope)",
      d.decision == BLOCKED and d.reason == Reason.CREDENTIAL_SCOPE_DENIED)
# regression: a caller asserting a BENIGN granted scope must NOT mask the constitution's required scope
d = decide(POLICY, action="export_customer_data", human_approved=True, usd_estimate=0.0,
           joules_estimate=10, runtime_seconds=2, credential_scope="nvidia:telemetry:read")
check("still BLOCKED when caller asserts a benign granted scope (no mask bypass)",
      d.decision == BLOCKED and d.reason == Reason.CREDENTIAL_SCOPE_DENIED)

print("\n(7) public action escalates to a human")
d = decide(POLICY, action="public_post", human_approved=False, usd_estimate=0.0, joules_estimate=10, runtime_seconds=2)
check("ESCALATE public_action_requires_review", d.decision == ESCALATE and d.reason == Reason.PUBLIC_ACTION_REQUIRES_REVIEW)

print("\n(8) missing required approval escalates")
d = decide(POLICY, action="call_api_model", human_approved=False, usd_estimate=42.0, joules_estimate=10, runtime_seconds=2)
check("ESCALATE human_approval_missing", d.decision == ESCALATE and d.reason == Reason.HUMAN_APPROVAL_MISSING)

print("\n(9) unknown action blocked")
d = decide(POLICY, action="delete_production_db", human_approved=True)
check("BLOCKED action_not_allowed", d.decision == BLOCKED and d.reason == Reason.ACTION_NOT_ALLOWED)

print("\n(10) override works ONLY when the constitution grants it")
override = Policy(agent_id="x", policy_version="v", limits=POLICY.limits,
                  approvals=Approvals(human_required=True, human_can_override_usd=False, human_can_override_joules=True),
                  actions=POLICY.actions, treasury=POLICY.treasury, credentials=POLICY.credentials)
d = evaluate(override, ActionRequest(action="large_gpu_job", human_approved=True, joules_estimate=18400, runtime_seconds=20))
check("joule override granted + human approved -> ALLOWED", d.decision == ALLOWED and d.reason == Reason.WITHIN_POLICY)
d = evaluate(override, ActionRequest(action="large_gpu_job", human_approved=False, joules_estimate=18400, runtime_seconds=20))
check("override still needs approval (not approved -> blocked)", d.decision == BLOCKED and d.reason == Reason.JOULE_CAP_EXCEEDED)

print("\n(11) per-agent actor + decision schema + ledger receipts")
d = decide(POLICY, action="call_api_model", actor="hermes.agent.operator", human_approved=True,
           usd_estimate=42.0, joules_estimate=100, runtime_seconds=5)
check("actor flows onto the decision/receipt agent", d.agent == "hermes.agent.operator")
dd = d.as_dict()
check("decision exposes schema keys",
      all(k in dd for k in ["agent", "policy_version", "action", "decision", "reason", "usd_cap", "joules_cap", "runtime_cap"]))
with tempfile.TemporaryDirectory() as td:
    led = Ledger(Path(td) / "events.jsonl")
    r1 = led.write(d)
    r2 = led.write(decide(POLICY, action="large_gpu_job", actor="hermes.agent.researcher", human_approved=True,
                          joules_estimate=18400, runtime_seconds=20))
    got = led.read_all()
    check("ledger writes + reads JSONL", len(got) == 2)
    check("receipt ids are landauer://receipt/NNN",
          r1["receipt_id"] == "landauer://receipt/001" and r2["receipt_id"] == "landauer://receipt/002")
    check("receipt carries all ledger fields + agent_id", all(k in got[0] for k in LEDGER_FIELDS)
          and got[1]["agent_id"] == "hermes.agent.researcher")

print("\n(12) every canonical reason code is reachable")
missing = [r for r in ALL_REASONS if r not in _seen]
check(f"all {len(ALL_REASONS)} reason codes exercised (missing: {missing})", not missing)

print("\n" + ("ALL PASS ✓" if _ok else "SOME FAILED ✗"))
raise SystemExit(0 if _ok else 1)
