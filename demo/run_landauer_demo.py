#!/usr/bin/env python3
"""demo/run_landauer_demo.py — the Landauer hackathon demo (Hermes + NVIDIA + Stripe + Landauer).

Each scenario: a Hermes agent proposes an action, Landauer gates it against the runtime constitution
BEFORE any side effect, allowed actions actually execute (real Stripe test charge / real GPU joules),
and every decision is written as a receipt to the Reality Ledger.

    Hermes decides what to do, NVIDIA tells us what compute it costs, Stripe accounts for what it
    spends, and Landauer decides whether the action is allowed.

Usage (from repo root):
    python demo/run_landauer_demo.py
    python demo/run_landauer_demo.py --no-real-stripe --no-real-hermes --mock-nvidia --gpu-seconds 6
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # box-drawing/em-dash output must not crash a cp1252 console
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from landauer import ALLOWED, BLOCKED, ESCALATE, ActionRequest, Ledger, Reason, evaluate, load_policy
from landauer.adapters import gpu_workload, hermes as hermes_adapter, nvidia
from landauer.adapters.stripe_budget import StripeBudgetAdapter
from hermes_bridge import hermes_available

HERMES_WIN = os.environ.get(
    "HERMES_PATH", r"C:\Users\BB2SM\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe")
POWER_EST_W = 285.0  # TGP — conservative MODELED power for the pre-execution joule projection (never under real draw)

# ---------------------------------------------------------------- pretty panels
_ANSI = {"green": "92", "red": "91", "yellow": "93", "cyan": "96", "gold": "33", "dim": "2", "bold": "1"}


def _c(text: str, color: str | None) -> str:
    if not color or color not in _ANSI:
        return text
    return f"\033[{_ANSI[color]}m{text}\033[0m"


def _decision_color(decision: str) -> str:
    return {"allowed": "green", "blocked": "red", "escalate": "yellow"}.get(decision, "cyan")


def panel(title: str, rows: list[tuple[str, str, str | None]], width: int = 60) -> None:
    bar = "─" * (width - 2)
    print("┌" + bar + "┐")
    print("│ " + title.ljust(width - 3) + "│")
    print("├" + bar + "┤")
    inner = width - 3
    for label, value, color in rows:
        label_str = f"{label:<17}"
        avail = inner - len(label_str)
        val = value if len(value) <= avail else (value[:max(0, avail - 1)] + "…")
        pad = max(0, inner - len(label_str) - len(val))
        print("│ " + label_str + _c(val, color) + (" " * pad) + "│")
    print("└" + bar + "┘")


def _short(p) -> str:
    p = Path(p)
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return p.name


def preflight_panel(policy_path: str, hermes_disp, gpu_disp, treasury_mode: str) -> None:
    """Live-checked sponsor/system roles — the first thing a judge sees: who proposes the work, who
    enforces the constitution, who proves the spend, who proves the compute, and where receipts go."""
    tre = ("Stripe TEST", "green") if treasury_mode == "test" else ("simulated (no test key)", "yellow")
    panel("LANDAUER LIVE DEMO — PREFLIGHT (1/2)", [
        ("Agent runtime:", hermes_disp[0], hermes_disp[1]),
        ("Proposal format:", "structured JSON", None),
        ("Policy source:", _short(policy_path), "cyan"),
        ("Treasury:", tre[0], tre[1]),
        ("GPU telemetry:", gpu_disp[0], gpu_disp[1]),
        ("Ledger:", "JSONL receipts (per decision)", None),
    ])


def constitution_panel(policy, treasury_mode: str = "test") -> None:
    tre = "Stripe test" if treasury_mode == "test" else "simulated, no test key"
    panel("LANDAUER RUNTIME CONSTITUTION (2/2)  ·  " + policy.policy_version, [
        ("Agent:", policy.agent_id, "cyan"),
        ("Treasury:", f"${policy.treasury.budget_usd:.2f} {policy.treasury.currency} ({tre})", None),
        ("Max USD/task:", f"${policy.limits.max_usd_per_task:.2f}", None),
        ("Max joules:", f"{policy.limits.max_joules_per_task:,.0f} J", None),
        ("Max runtime:", f"{policy.limits.max_runtime_seconds:.0f} s", None),
        ("Human required:", str(policy.approvals.human_required).upper(), None),
        ("Override USD/J:", f"{policy.approvals.human_can_override_usd} / {policy.approvals.human_can_override_joules}  (cap below the human)", None),
    ])


def decision_panel(act_title: str, decision, receipt_id: str, extra: list[tuple[str, str, str | None]]):
    usd_line = "—"
    if decision.usd_estimate is not None:
        verdict = "FAIL" if (decision.usd_cap is not None and decision.usd_estimate > decision.usd_cap) else "PASS"
        usd_line = f"${decision.usd_estimate:.2f} / ${decision.usd_cap:.2f} {verdict}"
    j_line = "—"
    if decision.joules_estimate is not None:
        verdict = "FAIL" if (decision.joules_cap is not None and decision.joules_estimate > decision.joules_cap) else "PASS"
        j_line = f"{decision.joules_estimate:,.0f} / {decision.joules_cap:,.0f} J {verdict}"
    rows = [
        ("Action:", decision.action, "cyan"),
        ("Human approval:", "YES" if decision.human_approved else "NO", None),
        ("USD budget:", usd_line, None),
        ("Joule budget:", j_line, None),
    ]
    rows += extra
    rows += [
        ("Decision:", decision.decision.upper(), _decision_color(decision.decision)),
        ("Reason:", decision.reason, _decision_color(decision.decision)),
        ("Receipt:", receipt_id, "dim"),
    ]
    panel(act_title, rows)
    print()


# ---------------------------------------------------------------- the run
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default=str(ROOT / "config" / "demo_policy.yaml"))
    ap.add_argument("--ledger", default=str(ROOT / "ledger" / "landauer_events.jsonl"))
    ap.add_argument("--real-stripe", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--real-hermes", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--mock-nvidia", action="store_true", help="force CPU workload (skip the real GPU load)")
    ap.add_argument("--gpu-seconds", type=float, default=12.0)
    ap.add_argument("--hermes-path", default=HERMES_WIN)
    ap.add_argument("--keep-ledger", action="store_true", help="append to the existing ledger instead of clearing")
    args = ap.parse_args()

    policy = load_policy(args.policy)
    ledger = Ledger(args.ledger)
    if not args.keep_ledger:
        ledger.clear()
    treasury = StripeBudgetAdapter(policy.treasury.budget_usd, allow_real=args.real_stripe)

    print(_c("\nLANDAUER — a runtime constitution for autonomous agents\n", "bold"))
    print("Hermes proposes the work · Landauer enforces the constitution · Stripe proves the spend · "
          "NVIDIA proves the compute · every decision leaves a receipt.\n")

    # ---- Preflight (1/2): live-checked sponsor/system roles ----
    if args.real_hermes:
        av = hermes_available(args.hermes_path)
        if av.get("available"):
            toks = (av.get("version") or "").split()
            ver = next((t for t in toks if t.startswith("v") and t[1:2].isdigit()), "")
            hermes_disp = (f"Hermes LIVE — hermes.exe {ver}".strip(), "green")
        else:
            hermes_disp = ("Hermes fallback — unreachable", "yellow")
    else:
        hermes_disp = ("Hermes fallback — --no-real-hermes", "yellow")

    real_gpu_load = nvidia.available() and gpu_workload.gpu_available() and not args.mock_nvidia
    if nvidia.available() and real_gpu_load:
        gpu_disp = ("NVIDIA nvidia-smi REAL · GPU load", "green")
    elif nvidia.available():
        gpu_disp = ("NVIDIA nvidia-smi REAL · CPU workload", "green")
    else:
        gpu_disp = ("MODELED fallback · no GPU", "yellow")

    preflight_panel(args.policy, hermes_disp, gpu_disp, treasury.mode)
    print(_c(f"   GPU: {nvidia.device_name()}", "dim"))
    print()

    # ---- Constitution (2/2): the human-defined rules the agent runs under ----
    constitution_panel(policy, treasury.mode)
    print(_c(f"   source: {_short(args.policy)}", "dim"))
    print()

    def gate_and_log(req: ActionRequest, title: str, *, on_allowed=None):
        """Evaluate -> (if allowed) execute side effect -> write receipt -> print panel."""
        decision = evaluate(policy, req)
        runtime = req.runtime_seconds
        extra: list[tuple[str, str, str | None]] = []
        if decision.decision == ALLOWED and on_allowed is not None:
            eff = on_allowed(decision) or {}
            extra = eff.get("extra", [])
            runtime = eff.get("runtime", runtime)
        else:
            if decision.reason == Reason.USD_CAP_EXCEEDED:
                extra.append(("Stripe:", "not charged — refused pre-execution", "red"))
            if req.note:
                extra.append(("Note:", req.note, "dim"))
        rec = ledger.write(decision, runtime_seconds=runtime)
        decision_panel(title, decision, rec["receipt_id"], extra)
        return decision

    # ---- Scenario A — Hermes proposes an API task; spend is under cap -> ALLOWED -> real Stripe charge
    print(_c("── Scenario A — allowed API action (Hermes + Stripe) ──", "gold"))
    proposal = hermes_adapter.propose_action(
        "Qualify a batch of inbound leads with one API model call. Keep spend small.",
        hermes_path=args.hermes_path, real=args.real_hermes)
    raw_usd = float(proposal.get("usd_estimate", 0.84) or 0.84)
    usd_a = max(min(raw_usd, 0.99), 0.50)  # clamp to a real Stripe-chargeable amount, under the $1.00 cap
    _src = proposal.get("source")
    src_disp = _c("Hermes LIVE", "green") if _src == "hermes" else _c("Hermes fallback", "yellow")
    _json_view = json.dumps({k: proposal.get(k) for k in
                             ("action", "usd_estimate", "joules_estimate", "runtime_seconds") if k in proposal})
    print(f"   {src_disp} (hermes.exe) proposed a structured action:")
    print(_c(f"     {_json_view}", "cyan"))
    if proposal.get("rationale"):
        print(f"     rationale: {str(proposal['rationale'])[:62]}")
    print(f"   → Landauer gates it as call_api_model @ ${usd_a:.2f} "
          f"(clamped to a Stripe-chargeable amount under the ${policy.limits.max_usd_per_task:.2f} cap)\n")

    def _charge(decision):
        res = treasury.charge(usd_a, "Landauer demo — allowed API model call")
        decision.stripe_object_id = res["stripe_object_id"]
        tag = "REAL" if res["real"] else "sim"
        return {"extra": [
            ("Stripe mode:", treasury.mode, None),
            ("Charged:", f"${usd_a:.2f}  [{tag}]  remaining ${res['remaining']:.2f}", "green" if res["real"] else "yellow"),
            ("Stripe id:", res["stripe_object_id"], "cyan"),
        ]}

    gate_and_log(ActionRequest(action="call_api_model", human_approved=True, usd_estimate=usd_a,
                               joules_estimate=0.0, runtime_seconds=3.0), "ACTION: call_api_model",
                 on_allowed=_charge)

    # ---- Scenario B — Hermes proposes an expensive API task -> BLOCKED before any spend
    print(_c("── Scenario B — blocked API overspend (Stripe cap below the human) ──", "gold"))
    gate_and_log(ActionRequest(action="call_api_model", human_approved=True, usd_estimate=1.40,
                               joules_estimate=0.0, runtime_seconds=3.0,
                               note="retried larger — $1.40 > $1.00 cap"),
                 "ACTION: call_api_model (expensive)")

    # ---- Scenario C — Hermes proposes local GPU work; projection under cap -> ALLOWED -> measure REAL joules
    print(_c("── Scenario C — allowed local compute (Hermes + NVIDIA, REAL joules) ──", "gold"))
    use_gpu = nvidia.available() and gpu_workload.gpu_available() and not args.mock_nvidia
    safe_s = policy.limits.max_joules_per_task / POWER_EST_W            # window that keeps the projection under cap
    c_seconds = min(args.gpu_seconds, max(2.0, safe_s - 1.0))           # guarantee the 'allowed compute' proof shot
    if c_seconds < args.gpu_seconds:
        print(f"   (clamped this scene to {c_seconds:.0f}s so the projection stays under the "
              f"{policy.limits.max_joules_per_task:,.0f} J cap — the 'allowed compute' shot is guaranteed)\n")
    proj_c = nvidia.project_joules(POWER_EST_W, c_seconds)             # E ≈ P·t conservative projection for the gate

    def _measure(decision):
        if use_gpu:
            tele = nvidia.measure(lambda: gpu_workload.gpu_matmul_load(c_seconds),
                                  action_id="run_local_model", fallback_duration_s=c_seconds)
            wl = "GPU matmul"
        else:
            tele = nvidia.measure(lambda: gpu_workload.cpu_fallback_load(c_seconds),
                                  action_id="run_local_model", fallback_duration_s=c_seconds)
            wl = "CPU fallback (no torch/CUDA)"
        decision.nvidia_telemetry = {k: tele[k] for k in
                                     ("joules", "avg_w", "peak_c", "samples", "source", "is_real", "device")}
        is_real = tele["source"] == "nvidia-smi"
        src = "REAL nvidia-smi" if is_real else "MODELED fallback"
        label = "Measured (REAL):" if is_real else "Estimated (MODELED):"
        extra = [
            ("Workload:", wl, None),
            (label, f"{tele['joules']:,.0f} J  ∫P·dt  [{src}]", "green" if is_real else "yellow"),
            ("Avg power / peak:", f"{tele['avg_w']:.1f} W / {tele['peak_c']:.0f} °C ({tele['samples']} samples)", None),
            ("Runtime:", f"{tele['runtime_s']:.1f} s wall", None),
        ]
        if tele.get("telemetry_incomplete"):
            extra.append(("⚠ telemetry:", "incomplete (nvidia-smi returned <2 samples)", "yellow"))
        return {"runtime": tele["runtime_s"], "extra": extra}

    gate_and_log(ActionRequest(action="run_local_model", human_approved=True, usd_estimate=0.0,
                               joules_estimate=proj_c, runtime_seconds=args.gpu_seconds, joules_measured=False,
                               note="projected from the agent's planned GPU job"),
                 "ACTION: run_local_model", on_allowed=_measure)

    # ---- Scenario D/E — big GPU job; human approves, but the joule projection exceeds the cap -> BLOCKED.
    #      This single panel satisfies both the handoff's D (blocked GPU) and E (human approval not sufficient).
    print(_c("── Scenario D/E — human approval is NOT sufficient: approved YES, joule cap FAIL → BLOCKED ──", "gold"))
    proj_d = nvidia.project_joules(POWER_EST_W, 25.0)  # ~7,125 J projected (> 5,000 cap)
    gate_and_log(ActionRequest(action="large_gpu_job", human_approved=True, usd_estimate=0.0,
                               joules_estimate=proj_d, runtime_seconds=25.0,
                               note="human approved — joule cap refuses"),
                 "ACTION: large_gpu_job (human-approved)")

    # ---- Autonomy montage: many actions decided by policy, humans pulled in only on escalate
    print(_c("── Autonomy montage — policy-defined autonomy (humans re-engaged only on ESCALATE) ──", "gold"))
    print("   (actions are session pre-authorized; the human is pulled back in only where policy escalates)\n")
    montage = [
        ActionRequest(action="summarize_docs", human_approved=True, usd_estimate=0.0, joules_estimate=40, runtime_seconds=2),
        ActionRequest(action="call_api_model", human_approved=True, usd_estimate=1.40, joules_estimate=0, runtime_seconds=3),
        ActionRequest(action="run_local_model", human_approved=True, usd_estimate=0.0, joules_estimate=1800, runtime_seconds=8),
        ActionRequest(action="public_post", human_approved=False, usd_estimate=0.0, joules_estimate=10, runtime_seconds=1),
        # credential_scope NOT supplied — the constitution's required_credential_scope drives the denial:
        ActionRequest(action="export_customer_data", human_approved=True, usd_estimate=0.0, joules_estimate=20, runtime_seconds=2),
        ActionRequest(action="large_gpu_job", human_approved=True, usd_estimate=0.0, joules_estimate=9000, runtime_seconds=40),
    ]
    for req in montage:
        d = evaluate(policy, req)
        rec = ledger.write(d, runtime_seconds=req.runtime_seconds)
        verb = _c(f"{d.decision.upper():8}", _decision_color(d.decision))
        print(f"   {req.action:22} → {verb} {d.reason:32} [{rec['receipt_id']}]")
    print()

    # ---- Close
    rows = ledger.read_all()
    counts = {}
    for r in rows:
        counts[r["decision"]] = counts.get(r["decision"], 0) + 1
    print(_c("── Reality Ledger ──", "gold"))
    print(f"   {len(rows)} receipts written → {args.ledger}")
    print(f"   {counts.get('allowed',0)} allowed · {counts.get('blocked',0)} blocked · {counts.get('escalate',0)} escalate")
    print(f"   View: python demo/show_ledger.py\n")
    print(_c("Humans set the rules. Agents do the work. Landauer leaves the receipt.", "bold"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
