#!/usr/bin/env python3
"""demo/run_landauer_demo.py — Landauer judge-facing terminal demo (Hermes + NVIDIA + Stripe + Landauer).

A polished, deterministic, recordable run that makes the product instantly legible:

    Hermes proposes the work · Landauer enforces the constitution · Stripe proves the spend ·
    NVIDIA proves the compute · every decision leaves a receipt.

Flow: intro → constitution card → five decision cards (allowed Stripe, blocked overspend, allowed real
GPU compute, human-approved-but-joule-blocked, public action escalated) → receipt replay → per-agent
resource accounting → Reality Ledger scoreboard.

Real adapters are reused: real Stripe test-mode PaymentIntents, real nvidia-smi ∫P·dt telemetry, a tight
no-skill Hermes proposer. Everything falls back to an honestly-labeled mode if a system is unavailable.

Usage (from repo root):
    python demo/run_landauer_demo.py
    python demo/run_landauer_demo.py --no-real-stripe --no-real-hermes --mock-nvidia --no-anim
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # box-drawing/em-dash output must not crash a cp1252 console
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from landauer import ALLOWED, BLOCKED, ESCALATE, ActionRequest, Ledger, evaluate, load_policy
from landauer.adapters import gpu_workload, hermes as hermes_adapter, nvidia
from landauer.adapters.stripe_budget import StripeBudgetAdapter
from hermes_bridge import hermes_available

HERMES_WIN = os.environ.get(
    "HERMES_PATH", r"C:\Users\BB2SM\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe")
POWER_EST_W = 285.0   # TGP — conservative MODELED power for the pre-execution joule projection

OPERATOR = "hermes.agent.operator"
RESEARCHER = "hermes.agent.researcher"
PUBLISHER = "hermes.agent.publisher"
VERB = {ALLOWED: "ALLOW", BLOCKED: "BLOCK", ESCALATE: "ESCALATE"}

_ANSI = {"green": "92", "red": "91", "yellow": "93", "cyan": "96", "gold": "33", "goldb": "1;33", "dim": "2", "bold": "1"}


def _c(text: str, color: str | None) -> str:
    if not color or color not in _ANSI:
        return text
    return f"\033[{_ANSI[color]}m{text}\033[0m"


def _decision_color(decision: str) -> str:
    return {ALLOWED: "green", BLOCKED: "red", ESCALATE: "yellow"}.get(decision, "cyan")


_HOLD_MODE = "normal"   # set by main(): "off" (--no-anim) | "normal" | "presentation" (--presentation)


def _hold(normal: float = 0.8, *, pres: float | None = None) -> None:
    """Pause for recordability. normal mode -> `normal` s; presentation -> `pres` (or `normal`); off -> 0."""
    if _HOLD_MODE == "off":
        return
    secs = (pres if pres is not None else normal) if _HOLD_MODE == "presentation" else normal
    if secs > 0:
        time.sleep(secs)


# ---------------------------------------------------------------- rendering
def rule(text: str) -> None:
    print(_c(f"\n── {text} ──", "gold"))


def card(title: str, rows: list[tuple[str, str, str | None]], width: int = 58) -> None:
    print("┌─ " + title + " " + "─" * max(0, width - 5 - len(title)) + "┐")
    inner = width - 3
    for label, value, color in rows:
        label_str = f"{label:<16}"
        avail = inner - len(label_str)
        val = value if len(value) <= avail else value[:max(0, avail - 1)] + "…"
        pad = max(0, inner - len(label_str) - len(val))
        print("│ " + label_str + _c(val, color) + " " * pad + "│")
    print("└" + "─" * (width - 2) + "┘")


def banner() -> None:
    w = 48
    def ln(t: str) -> str:
        return "│" + t.center(w - 2) + "│"
    print(_c("╭" + "─" * (w - 2) + "╮", "gold"))
    print(_c(ln("LANDAUER"), "bold"))
    print(ln("Runtime Constitution for Hermes Agents"))
    print(_c("╰" + "─" * (w - 2) + "╯", "gold"))


def _check_lines(policy, hermes_disp, stripe_mode, gpu_state):
    lim = policy.limits
    return [
        (f"Constitution loaded — {policy.policy_version}", "green"),
        (f"Caps armed — ${lim.max_usd_per_task:,.0f} / {lim.max_joules_per_task:,.0f} J / {lim.max_runtime_seconds:.0f} s", "green"),
        (f"Credential scopes loaded ({len(policy.credentials.allowed_scopes)})", "green"),
        (f"Hermes runtime: {hermes_disp[0]}", hermes_disp[1]),
        (f"Stripe treasury: {stripe_mode[0]}", stripe_mode[1]),
        (f"NVIDIA telemetry: {gpu_state[0]}", gpu_state[1]),
        ("Reality Ledger armed", "green"),
    ]


def intro(policy, hermes_disp, stripe_mode, gpu_state, no_anim: bool) -> None:
    def s(t: float):
        if not no_anim:
            time.sleep(t)
    banner()
    print()
    for line in ("Hermes proposes actions.", "Stripe accounts for spend.",
                 "NVIDIA measures compute.", "Landauer enforces the cap."):
        print("  " + line); s(0.14)
    print("\nInitializing..."); s(0.25)
    for text, col in _check_lines(policy, hermes_disp, stripe_mode, gpu_state):
        print("  " + _c("✓", col) + " " + _c(text, col)); s(0.26)
    print()


_BLOCK = {
    "L": ["█    ", "█    ", "█    ", "█    ", "█████"],
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"],
    "N": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "D": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "U": ["█   █", "█   █", "█   █", "█   █", " ███ "],
    "E": ["█████", "█    ", "███  ", "█    ", "█████"],
    "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
}


def _ascii_title(word: str) -> list[str]:
    return [" ".join(_BLOCK[ch][r] for ch in word) for r in range(5)]


def opener(policy) -> None:
    W = 88
    inner = W - 2
    GOLD, GOLDB = "gold", "goldb"
    lim = policy.limits

    def frow(left, right=None):
        lvis = sum(len(t) for t, _ in left)
        lbody = "".join(_c(t, c) for t, c in left)
        if right is not None:
            rvis = sum(len(t) for t, _ in right)
            rbody = "".join(_c(t, c) for t, c in right)
            return _c("│", GOLD) + lbody + " " * max(1, inner - lvis - rvis) + rbody + _c("│", GOLD)
        return _c("│", GOLD) + lbody + " " * max(0, inner - lvis) + _c("│", GOLD)

    blank = _c("│" + " " * inner + "│", GOLD)
    title = _ascii_title("LANDAUER")
    controls = [
        ("spend caps", "cap on $ spend per agent action  (Stripe-backed)"),
        ("joule caps", "cap on compute energy per action  (NVIDIA ∫P·dt)"),
        ("credential scopes", "only constitution-granted scopes may be used"),
        ("runtime limits", "cap on wall-clock seconds per action"),
        ("public-action review", "outward / irreversible actions routed to a human"),
        ("receipt ledger", "every decision written as an auditable receipt"),
    ]
    status = (f"{policy.policy_version} · ${lim.max_usd_per_task:,.0f} cap · "
              f"{lim.max_joules_per_task:,.0f} J cap · {lim.max_runtime_seconds:.0f} s · ")
    pill = "\033[30;42m RTX AI Garage \033[0m"            # green pill (black on green)
    badges_vis = len("NOUS × NVIDIA") + 3 + len(" RTX AI Garage ")

    print(_c("┌" + "─" * inner + "┐", GOLD))
    print(blank)
    print(frow([("   ", None), (title[0], GOLDB)], [("Runtime Constitution v1   ", "gold")]))
    print(frow([("   ", None), (title[1], GOLDB)], [(f"policy {policy.policy_version}   ", "dim")]))
    print(frow([("   ", None), (title[2], GOLDB)]))
    print(frow([("   ", None), (title[3], GOLDB)]))
    print(frow([("   ", None), (title[4], GOLDB)]))
    print(blank)
    print(frow([("   ", None), ("Available Controls", GOLDB)]))
    for label, desc in controls:
        print(frow([("     ", None), (f"{label:<22}", GOLD), (desc, "dim")]))
    print(blank)
    print(frow([("   ", None), ("Backed by   ", GOLDB),
                ("Hermes Runtime · Stripe Treasury · NVIDIA Telemetry · Reality Ledger", "gold")]))
    print(blank)
    print(frow([("   ", None), ("Humans set the constitution.", "gold")]))
    print(frow([("   ", None), ("Hermes agents do the work.", "gold")]))
    print(frow([("   ", None), ("Landauer leaves the receipt.", GOLDB)]))
    print(blank)
    print(frow([("   ", None), (status, "dim"), ("ready", "green")]))
    print(_c("│", GOLD) + " " * max(1, inner - badges_vis) + _c("NOUS × NVIDIA", GOLDB) + "   " + pill + _c("│", GOLD))
    print(blank)
    print(_c("└" + "─" * inner + "┘", GOLD))
    _hold(4.5)


def system_map() -> None:
    w = 64
    inner = w - 2
    def line(content: str, color: str) -> str:
        return _c("│", "gold") + _c(content.ljust(inner), color) + _c("│", "gold")
    print(_c("╭─ System Map " + "─" * (w - 15) + "╮", "gold"))
    print(_c("│" + " " * inner + "│", "gold"))
    for content, col in [
        ("   Hermes agent proposes action", "cyan"),
        ("            ↓", "dim"),
        ("   Landauer checks policy before execution", "cyan"),
        ("            ↓", "dim"),
        ("   Stripe accounts for spend   ·   NVIDIA measures compute", "cyan"),
        ("            ↓", "dim"),
        ("   Reality Ledger writes receipt", "cyan"),
    ]:
        print(line(content, col))
    print(_c("│" + " " * inner + "│", "gold"))
    print(_c("╰" + "─" * inner + "╯", "gold"))
    _hold(4.5)


def preflight(policy, hermes_disp, stripe_mode, gpu_state) -> None:
    rule("Preflight — live system checks")
    for text, col in _check_lines(policy, hermes_disp, stripe_mode, gpu_state):
        print("  " + _c("✓", col) + " " + _c(text, col))
    print()
    _hold(3.5)


def constitution_card(policy) -> None:
    card("LANDAUER CONSTITUTION", [
        ("Policy:", policy.policy_version, "cyan"),
        ("USD cap:", f"${policy.limits.max_usd_per_task:,.2f} / action", None),
        ("Joule cap:", f"{policy.limits.max_joules_per_task:,.0f} J / action", None),
        ("Runtime cap:", f"{policy.limits.max_runtime_seconds:.0f} s / action", None),
        ("Public actions:", "require human review", None),
        ("Override USD/J:", "off / off  (cap below the human)", None),
        ("Cred scopes:", f"{len(policy.credentials.allowed_scopes)} granted", None),
    ])
    for sc in policy.credentials.allowed_scopes:
        print(_c(f"     · {sc}", "dim"))
    print()
    _hold(0.8, pres=4.5)


def decision_card(*, proposal: str, actor: str, decision: str, reason: str, receipt: str,
                  usd=None, usd_cap=None, joules=None, joules_cap=None, joules_label: str = "",
                  stripe_obj: str | None = None, human_approved: bool = False) -> None:
    col = _decision_color(decision)
    rows = [
        ("Proposal:", proposal, "cyan"),
        ("Agent:", actor, None),
        ("Decision:", VERB.get(decision, decision.upper()), col),
        ("Reason:", reason, col),
    ]
    if usd is not None:
        rows.append(("USD:", f"${usd:,.2f} / ${usd_cap:,.2f}", None))
    if joules is not None:
        tag = f" {joules_label}" if joules_label else ""
        rows.append(("Joules:", f"{joules:,.0f} J{tag} / {joules_cap:,.0f} J cap", None))
    if stripe_obj:
        rows.append(("Stripe obj:", f"{stripe_obj} (test)", "cyan"))
    if decision == BLOCKED and human_approved:
        rows.append(("Human approval:", "present — not sufficient", col))
    elif decision == ESCALATE:
        rows.append(("Human approval:", "required — routed to human", col))
    rows.append(("Receipt:", receipt, "dim"))
    card("LANDAUER DECISION", rows)
    print()
    _hold(0.8, pres=6.0)


def receipt_replay(record: dict) -> None:
    rule(f"Receipt replay — {record['receipt_id']}")
    replay = {
        "decision": record["decision"],
        "reason_code": record["reason"],
        "agent_id": record["agent_id"],
        "human_approval": record["human_approved"],
        "policy_cap_joules": record["joules_cap"],
        "estimated_joules": record["joules_estimate"],
        "timestamp": record["timestamp"],
        "receipt_id": record["receipt_id"],
    }
    print(_c(json.dumps(replay, indent=2), "cyan"))
    print()
    _hold(0.8, pres=4.0)


def accounting_table(results: list[dict]) -> None:
    rule("Per-agent resource accounting")
    agg: dict[str, dict] = {}
    for r in results:
        a = agg.setdefault(r["actor"], {"usd": 0.0, "joules": 0.0, "proj": False,
                                        ALLOWED: 0, BLOCKED: 0, ESCALATE: 0})
        a["usd"] += r["usd_spent"]
        a["joules"] += r["joules"]
        a["proj"] = a["proj"] or r["projected"]
        a[r["decision"]] += 1
    print(_c(f"   {'agent_id':<26}{'usd_spent':<12}{'joules_used':<14}{'allowed':<9}{'blocked':<9}{'escalated':<9}", "dim"))
    for actor, a in agg.items():
        usd_str = f"${a['usd']:,.2f}"
        j_str = f"{a['joules']:,.0f} J" + ("*" if a["proj"] else "")
        print(f"   {actor:<26}{usd_str:<12}{j_str:<14}{a[ALLOWED]:<9}{a[BLOCKED]:<9}{a[ESCALATE]:<9}")
    print(_c("   * projected or modeled (not a real measurement)", "dim"))
    print(_c("   As agent autonomy and spend grow, companies must see compute usage PER AGENT —", "yellow"))
    print(_c("   not only cloud/API spend.", "yellow"))
    print()
    _hold(0.8, pres=6.0)


def scoreboard(results: list[dict]) -> None:
    rule("LANDAUER REALITY LEDGER")
    mark = {ALLOWED: ("✓", "green"), BLOCKED: ("✕", "red"), ESCALATE: ("!", "yellow")}
    for r in results:
        m, col = mark[r["decision"]]
        print(_c(f"   {m} {r['label']:<34}{r['reason']}", col))
    n = len(results)
    a = sum(1 for r in results if r["decision"] == ALLOWED)
    b = sum(1 for r in results if r["decision"] == BLOCKED)
    e = sum(1 for r in results if r["decision"] == ESCALATE)
    print()
    print(f"   {n} proposals checked · " + _c(f"{a} allowed", "green") + " · "
          + _c(f"{b} blocked", "red") + " · " + _c(f"{e} escalated", "yellow")
          + f" · {n} receipts written")
    _hold(0.8, pres=2.0)


def end_card() -> None:
    w = 44
    def ln(t: str) -> str:
        return "│" + t.center(w - 2) + "│"
    print()
    print(_c("╭" + "─" * (w - 2) + "╮", "gold"))
    print(_c(ln("Humans set the constitution."), "bold"))
    print(_c(ln("Hermes agents do the work."), "bold"))
    print(_c(ln("Landauer leaves the receipt."), "bold"))
    print(_c("╰" + "─" * (w - 2) + "╯", "gold"))
    _hold(1.0, pres=6.0)


# ---------------------------------------------------------------- the run
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default=str(ROOT / "config" / "demo_policy.yaml"))
    ap.add_argument("--ledger", default=str(ROOT / "ledger" / "landauer_events.jsonl"))
    ap.add_argument("--real-stripe", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--real-hermes", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--mock-nvidia", action="store_true", help="force CPU workload (skip the real GPU load)")
    ap.add_argument("--gpu-seconds", type=float, default=2.5, help="allowed-compute window (kept under the joule cap)")
    ap.add_argument("--hermes-path", default=HERMES_WIN)
    ap.add_argument("--no-anim", action="store_true", help="skip the intro timing (for re-takes / CI)")
    ap.add_argument("--presentation", action="store_true",
                    help="cinematic recording mode: opener art, system map, long per-section holds")
    ap.add_argument("--keep-ledger", action="store_true", help="append instead of clearing the ledger")
    args = ap.parse_args()

    global _HOLD_MODE
    _HOLD_MODE = "off" if args.no_anim else ("presentation" if args.presentation else "normal")

    policy = load_policy(args.policy)
    ledger = Ledger(args.ledger)
    if not args.keep_ledger:
        ledger.clear()
    treasury = StripeBudgetAdapter(policy.treasury.budget_usd, allow_real=args.real_stripe)
    cap_usd = policy.limits.max_usd_per_task
    cap_j = policy.limits.max_joules_per_task

    # --- live-system states (honest; drive the intro checks). One Hermes probe, reused below. ---
    av = hermes_available(args.hermes_path) if args.real_hermes else {"available": False}
    if args.real_hermes and av.get("available"):
        toks = (av.get("version") or "").split()
        ver = next((t for t in toks if t.startswith("v") and t[1:2].isdigit()), "")
        hermes_disp = (f"LIVE — hermes.exe {ver}".strip(), "green")
    elif args.real_hermes:
        hermes_disp = ("fallback — unreachable", "yellow")
    else:
        hermes_disp = ("fallback — deterministic", "yellow")
    stripe_mode = (("TEST mode", "green") if treasury.mode == "test" else ("simulated (no test key)", "yellow"))
    real_gpu = nvidia.available() and gpu_workload.gpu_available() and not args.mock_nvidia
    gpu_state = (("nvidia-smi REAL · GPU load", "green") if real_gpu
                 else ("nvidia-smi REAL · CPU workload", "green") if nvidia.available()
                 else ("MODELED fallback · no GPU", "yellow"))

    if args.presentation:
        opener(policy)
        system_map()
        preflight(policy, hermes_disp, stripe_mode, gpu_state)
    else:
        intro(policy, hermes_disp, stripe_mode, gpu_state, args.no_anim)
    constitution_card(policy)

    results: list[dict] = []

    # ---- Scenario 1 — operator: allowed API spend (Hermes LIVE proposal + real Stripe charge) ----
    rule("Scenario 1 — allowed API action  ·  Hermes → Stripe")
    proposal = hermes_adapter.propose_action(
        "Qualify a batch of inbound leads with one API model call.",
        hermes_path=args.hermes_path, real=args.real_hermes, available=av)
    psrc = _c("Hermes LIVE", "green") if proposal.get("source") == "hermes" else _c("Hermes fallback", "yellow")
    jview = json.dumps({k: proposal.get(k) for k in
                        ("action", "joules_estimate", "runtime_seconds") if k in proposal})
    print(f"   {OPERATOR}  →  proposes via {psrc} (hermes.exe):")
    print(_c(f"     {jview}", "cyan"))
    print(f"   → Landauer meters the spend at ${42.00:,.2f} (operator API tier) vs ${cap_usd:,.2f} cap …\n")
    req = ActionRequest(action="call_api_model", actor=OPERATOR, human_approved=True,
                        usd_estimate=42.00, joules_estimate=0.0, runtime_seconds=3)
    d = evaluate(policy, req)
    stripe_obj = None
    if d.is_allowed:
        res = treasury.charge(42.00, "Landauer demo — small API action")
        d.stripe_object_id = res["stripe_object_id"]
        stripe_obj = res["stripe_object_id"] if res["real"] else None
        if stripe_obj:
            print(_c(f"   Stripe TEST receipt: {stripe_obj} · $42.00 · succeeded (test)", "cyan"))
    rec = ledger.write(d, runtime_seconds=3)
    decision_card(proposal="stripe.small_api_action", actor=OPERATOR, decision=d.decision, reason=d.reason,
                  receipt=rec["receipt_id"], usd=42.00, usd_cap=cap_usd, stripe_obj=stripe_obj, human_approved=True)
    foot = ("test-mode payment object created; policy enforcement is real." if stripe_obj
            else "simulated treasury (no test key); policy enforcement is real.")
    print(_c(f"   ↳ {foot}\n", "dim"))
    results.append({"actor": OPERATOR, "label": "API action allowed", "decision": d.decision,
                    "reason": d.reason, "usd_spent": 42.00 if d.is_allowed else 0.0, "joules": 0, "projected": False})

    # ---- Scenario 2 — operator: blocked overspend ($4,800 > $500) ----
    rule("Scenario 2 — blocked API overspend  ·  Stripe cap below the human")
    print(f"   {OPERATOR}  →  proposes: stripe.large_api_action @ ${4800.00:,.2f}\n")
    req = ActionRequest(action="call_api_model", actor=OPERATOR, human_approved=True,
                        usd_estimate=4800.00, joules_estimate=0.0, runtime_seconds=3)
    d = evaluate(policy, req)
    rec = ledger.write(d, runtime_seconds=3)
    decision_card(proposal="stripe.large_api_action", actor=OPERATOR, decision=d.decision, reason=d.reason,
                  receipt=rec["receipt_id"], usd=4800.00, usd_cap=cap_usd, human_approved=True)
    print(_c("   ↳ no Stripe object created — refused pre-execution; policy enforcement is real.\n", "dim"))
    results.append({"actor": OPERATOR, "label": "Stripe overspend blocked", "decision": d.decision,
                    "reason": d.reason, "usd_spent": 0.0, "joules": 0, "projected": False})

    # ---- Scenario 3 — researcher: allowed local compute, REAL measured joules under cap ----
    rule("Scenario 3 — allowed local compute  ·  Hermes → NVIDIA (REAL joules)")
    safe_s = cap_j / POWER_EST_W
    c_seconds = min(args.gpu_seconds, max(1.5, safe_s - 0.5))   # keep the projection under the joule cap
    proj = nvidia.project_joules(POWER_EST_W, c_seconds)
    print(f"   {RESEARCHER}  →  proposes: gpu.small_inference (projected {proj:,.0f} J ≤ {cap_j:,.0f} J cap)\n")
    req = ActionRequest(action="run_local_model", actor=RESEARCHER, human_approved=True,
                        usd_estimate=0.0, joules_estimate=proj, runtime_seconds=c_seconds)
    d = evaluate(policy, req)
    tele = None
    if d.is_allowed:
        workload = gpu_workload.gpu_matmul_load if real_gpu else gpu_workload.cpu_fallback_load
        tele = nvidia.measure(lambda: workload(c_seconds), action_id="run_local_model",
                              fallback_duration_s=c_seconds)
        d.nvidia_telemetry = {k: tele[k] for k in
                              ("joules", "avg_w", "peak_c", "samples", "source", "is_real", "device")}
        d.joules_estimate = tele["joules"]                    # receipt records the REAL measured ∫P·dt …
        d.joules_measured = (tele["source"] == "nvidia-smi")  # … flagged measured when nvidia-smi is real
    rec = ledger.write(d, runtime_seconds=(tele["runtime_s"] if tele else c_seconds))
    is_real = bool(tele and tele["source"] == "nvidia-smi")
    measured_j = tele["joules"] if tele else 0.0
    decision_card(proposal="gpu.small_inference", actor=RESEARCHER, decision=d.decision, reason=d.reason,
                  receipt=rec["receipt_id"], joules=measured_j, joules_cap=cap_j,
                  joules_label=("measured" if is_real else "modeled"), human_approved=True)
    if tele:
        src = "REAL nvidia-smi" if is_real else "MODELED fallback"
        print(_c(f"   ↳ {tele['avg_w']:.1f} W avg · {tele['peak_c']:.0f} °C · {tele['samples']} samples "
                 f"· {tele['runtime_s']:.1f} s  [{src}]\n", "dim"))
    results.append({"actor": RESEARCHER, "label": "GPU job allowed", "decision": d.decision,
                    "reason": d.reason, "usd_spent": 0.0, "joules": measured_j, "projected": not is_real})

    # ---- Scenario 4 — researcher: human-approved, but joule projection exceeds cap -> BLOCKED ----
    rule("Scenario 4 — human approval is NOT sufficient  ·  joule cap below the human")
    print(f"   {RESEARCHER}  →  proposes: gpu.large_training (projected 18,400 J)\n")
    req = ActionRequest(action="large_gpu_job", actor=RESEARCHER, human_approved=True,
                        usd_estimate=0.0, joules_estimate=18400, runtime_seconds=20)
    d = evaluate(policy, req)
    rec_s4 = ledger.write(d, runtime_seconds=20)
    decision_card(proposal="gpu.large_training", actor=RESEARCHER, decision=d.decision, reason=d.reason,
                  receipt=rec_s4["receipt_id"], joules=18400, joules_cap=cap_j, joules_label="projected",
                  human_approved=True)
    print(_c("   ↳ a human approved this job — approval is not a bypass; the joule cap is enforced below the human.\n", "dim"))
    _hold(0.8, pres=3.0)
    results.append({"actor": RESEARCHER, "label": "Human-approved GPU job blocked", "decision": d.decision,
                    "reason": d.reason, "usd_spent": 0.0, "joules": 18400, "projected": True})

    # ---- Scenario 5 — publisher: public/irreversible action -> ESCALATE ----
    rule("Scenario 5 — public action escalated  ·  governs irreversible/public actions")
    print(f"   {PUBLISHER}  →  proposes: comms.public_broadcast (post publicly / external message)\n")
    req = ActionRequest(action="public_post", actor=PUBLISHER, human_approved=False,
                        usd_estimate=0.0, joules_estimate=12, runtime_seconds=1)
    d = evaluate(policy, req)
    rec = ledger.write(d, runtime_seconds=1)
    decision_card(proposal="comms.public_broadcast", actor=PUBLISHER, decision=d.decision, reason=d.reason,
                  receipt=rec["receipt_id"], joules=12, joules_cap=cap_j, joules_label="projected",
                  human_approved=False)
    print(_c("   ↳ Landauer governs irreversible/public actions, not only spend.\n", "dim"))
    results.append({"actor": PUBLISHER, "label": "Public action escalated", "decision": d.decision,
                    "reason": d.reason, "usd_spent": 0.0, "joules": 12, "projected": True})

    # ---- Receipt replay (the killer receipt) → per-agent accounting → scoreboard ----
    receipt_replay(rec_s4)
    accounting_table(results)
    scoreboard(results)
    end_card()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
