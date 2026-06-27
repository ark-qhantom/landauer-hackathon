#!/usr/bin/env python3
"""
test_caps.py — dual-cap governance regression for the Landauer engine.

Proves two non-negotiables of evaluate_guardrails:
  1. The original MONEY hard stop is intact and still survives --approve (no regression from the physics
     evolution); the energy cap is DORMANT when a run declares no energy_budget.
  2. The NEW ENERGY hard stop is an INDEPENDENT, cumulative cap that also survives --approve and blocks on
     physics alone (money fine) — proving the two caps are orthogonal.

Run:  python3 test_caps.py     (exit 0 = all pass)
"""

from protos_core import (Budget, EnergyBudget, Guardrails, ActionSensitivity, ActionPhysics,
                         ProposedAction, ProtosRun, parse_run, evaluate_run, evaluate_guardrails,
                         PhysicsEnergyModel)

_ok = True


def check(label: str, cond: bool):
    global _ok
    _ok = _ok and bool(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")


def _energy_run(intensity: float, duration_s: float, energy_limit_J: float,
                *, money_cost: float = 1.0, money_limit: float = 1000.0, n: int = 1) -> ProtosRun:
    """A run whose action(s) are cheap in money but governed by an energy cap (the orthogonality fixture)."""
    actions = [ProposedAction(
        id=f"train-{i}", title=f"Train at GPU load {intensity}", capability_need="local_model",
        est_cost_usd=money_cost, sensitivity=ActionSensitivity(involves_spend=True),
        physics=ActionPhysics(est_intensity=intensity, est_duration_s=duration_s),
    ) for i in range(n)]
    return ProtosRun(
        run_id="energy-test", name="energy cap test", goal="prove the physics cap",
        budget=Budget(monthly_limit_usd=money_limit),
        guardrails=Guardrails(),
        allowed_capabilities=["local_model"],
        offer_seed={"name": "x", "one_liner": "x"},
        proposed_actions=actions,
        energy_budget=EnergyBudget(monthly_energy_limit_joules=energy_limit_J),
    )


print("test_caps.py — dual-cap governance regression\n")

# (1) Canonical run now declares BOTH caps: money blocks one action, energy blocks another — orthogonally,
#     both surviving --approve. This is the headline demo beat.
print("(1) canonical run: money AND energy hard stops fire orthogonally, surviving --approve")
run = parse_run(open("bundle/runs/revenue-ops-seed-001.yaml").read())
rep = evaluate_guardrails(run, evaluate_run(run),
                          approved_ids=["scale-to-500-leads", "gpu-render-batch"])  # pre-approve BOTH
blocked_ids = {b.action_id for b in rep.blocked}
def _rules(aid):
    return {h.rule for h in next(i for i in rep.items if i.action_id == aid).hits}
check("scale-to-500-leads BLOCKED on MONEY despite --approve",
      "scale-to-500-leads" in blocked_ids and "budget_limit" in _rules("scale-to-500-leads"))
check("gpu-render-batch BLOCKED on ENERGY despite --approve",
      "gpu-render-batch" in blocked_ids and "energy_limit" in _rules("gpu-render-batch"))
check("gpu-render-batch blocked on energy ONLY — money was fine (caps orthogonal)",
      "budget_limit" not in _rules("gpu-render-batch"))
check("both caps tripped: budget_ok False AND energy_ok False",
      rep.budget_ok is False and rep.energy_ok is False)
check("energy cap active: energy_limit_joules == 50000", rep.energy_limit_joules == 50000)

# (2) ENERGY-only block: cheap money ($1 vs $1000), expensive energy (12000 J vs 5000 J cap), pre-approved.
print("\n(2) energy hard stop fires independently of money, survives --approve")
proj = PhysicsEnergyModel.estimate_energy(1.0, 60)   # (4.5 + 1.0*(285-4.5)) * 60 = 285W * 60s = 17100 J
run2 = _energy_run(intensity=1.0, duration_s=60, energy_limit_J=5000.0)
rep2 = evaluate_guardrails(run2, evaluate_run(run2), approved_ids=["train-0"])  # pre-approved!
item = next(i for i in rep2.items if i.action_id == "train-0")
rules = {h.rule for h in item.hits}
check(f"projected energy {proj:.0f} J exceeds the 5000 J cap", proj > 5000)
check("train-0 BLOCKED despite --approve", "train-0" in {b.action_id for b in rep2.blocked})
check("blocked on ENERGY (rule energy_limit present, budget_limit absent)",
      "energy_limit" in rules and "budget_limit" not in rules)
check("energy_ok False AND budget_ok True (caps are orthogonal)",
      rep2.energy_ok is False and rep2.budget_ok is True)

# (3) CUMULATIVE energy: two sub-limit actions whose sum exceeds the cap -> second blocks (like money).
print("\n(3) energy cap is cumulative (a running hard stop, like money)")
# each action: 0.5 intensity x 10s -> estimate_energy under the CALIBRATED 4070 envelope (idle 4.5 / max 285 W).
# cap 2000 J -> first fits, cumulative 2x exceeds -> second blocks. Computed from the model so the assertion
# tracks the calibrated envelope instead of a literal tied to the old 60/200 placeholders (was 1300 J).
_per = PhysicsEnergyModel.estimate_energy(0.5, 10)
run3 = _energy_run(intensity=0.5, duration_s=10, energy_limit_J=2000.0, n=2)
rep3 = evaluate_guardrails(run3, evaluate_run(run3))
b3 = {b.action_id for b in rep3.blocked}
check(f"first action fits ({_per:.0f} J < 2000 J cap, not blocked)", "train-0" not in b3)
check(f"second action blocked (cumulative {2*_per:.0f} J > 2000 J)", "train-1" in b3)
check(f"committed_energy reflects only the executable action ({_per:.0f} J)",
      abs(rep3.committed_energy_joules - _per) < 1e-6)

# (4) Sub-limit energy action is NOT over-blocked.
print("\n(4) sub-limit energy action passes (no false block)")
run4 = _energy_run(intensity=0.5, duration_s=10, energy_limit_J=5000.0)  # 1300 J < 5000
rep4 = evaluate_guardrails(run4, evaluate_run(run4))
check("under-cap action not blocked AND energy_ok True", not rep4.blocked and rep4.energy_ok is True)

# (5) Regression guarantee: a run that declares NO energy_budget has the energy cap DORMANT — even a huge
#     physics projection cannot block, and the money path is byte-identical to the pre-physics engine.
print("\n(5) energy cap DORMANT when a run declares no energy_budget (money path unchanged)")
no_e = ProtosRun(
    run_id="no-energy", name="no energy budget", goal="prove dormancy",
    budget=Budget(monthly_limit_usd=10.0), guardrails=Guardrails(),
    allowed_capabilities=["local_model"], offer_seed={"name": "x", "one_liner": "x"},
    proposed_actions=[ProposedAction(
        id="over", title="over money budget, huge energy", capability_need="local_model",
        est_cost_usd=20.0, sensitivity=ActionSensitivity(involves_spend=True),
        physics=ActionPhysics(est_intensity=1.0, est_duration_s=9999))],  # massive energy, but no cap declared
)  # energy_budget defaults to None
repx = evaluate_guardrails(no_e, evaluate_run(no_e), approved_ids=["over"])
check("money still blocks (20 > 10) even pre-approved", "over" in {b.action_id for b in repx.blocked})
check("energy dormant: energy_ok True, energy_limit_joules None, no energy_limit rule fired",
      repx.energy_ok is True and repx.energy_limit_joules is None
      and all(h.rule != "energy_limit" for i in repx.items for h in i.hits))

print("\n" + ("ALL PASS ✓" if _ok else "SOME FAILED ✗"))
raise SystemExit(0 if _ok else 1)
