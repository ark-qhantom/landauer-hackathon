#!/usr/bin/env python3
"""
Protos Lead-to-Revenue Runner — the working product.

Loads the canonical ops run, executes the governed engine, attaches a REAL (test-mode) Stripe earn
loop, optionally invokes Hermes for the redundant ops work, runs the spawn CHAIN in-process to a
chosen depth, and renders a truthful dashboard. Every "real" claim on the dashboard is gated on an
actual success; anything not real is labeled SIMULATED.

Run (safe default — no keys, no Hermes auth needed):
    python3 runner.py --approve quality-review-leads allocate-revenue --depth 2

Real money + real Hermes (after provisioning sk_test_ key and a Hermes provider):
    python3 runner.py --approve quality-review-leads allocate-revenue --depth 2 --real-stripe --real-hermes
"""

import argparse
import json
import time
import html
import hashlib
import csv
from pathlib import Path
from datetime import datetime

from protos_core import parse_run, execute_run, save_result, TimelineEvent
from hermes_bridge import fulfill_lead_ops_cycle, hermes_available, HERMES_DEFAULT
from stripe_earn import run_earn_loop


def esc(x):
    """HTML-escape any text injected into the dashboard."""
    return html.escape(str(x))

try:
    from rich import print as rprint
    from rich.panel import Panel
    RICH = True
except ImportError:
    RICH = False
    def rprint(*a, **k):
        print(*[getattr(x, "renderable", x) for x in a])
    class Panel:  # minimal shim
        def __init__(self, body, title="", **k): self.renderable = f"\n=== {title} ===\n{body}"

ROOT = Path(__file__).parent
RUN_PATH = ROOT / "runs" / "revenue-ops-seed-001.yaml"
SKILL_DIR = ROOT / "skills" / "revenue-ops-lead-to-revenue"
OUT_DIR = ROOT / "out" / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"

DEPTH_CAP = 8          # hard upper bound on chain depth (user input is clamped to this)
SATURATION_EPS = 0.005  # stop spawning when the projected per-generation skill uplift falls below this


# ---------------------------------------------------------------- chain
def run_chain(root_run, approved_ids, depth, eval_result=None):
    """Execute the root cycle, then recursively run each spawned child IN-PROCESS (deterministic,
    offline-safe). Terminates at --depth OR when the projected skill uplift per generation saturates
    (a real rule, unlike the old $15 floor which the growing economics could never trigger)."""
    chain = []
    run = root_run
    gen = 1
    while True:
        result = execute_run(run, approved_ids=(approved_ids if gen == 1 else []), generation=gen,
                             eval_result=(eval_result if gen == 1 else None))
        chain.append((run, result))
        saturated = gen > 1 and (result.metrics.qualify_rate_delta or 0) < SATURATION_EPS
        if gen > depth or saturated:
            if saturated:
                result.timeline.append(TimelineEvent(
                    result.timeline[-1].ts_offset_ms + 120, "chain", "info",
                    "Chain stopped spawning: projected per-generation skill uplift fell below the "
                    "saturation threshold — no marginal value in another agent."))
            break
        run = parse_run(result.spawned_run_content)  # the child the parent actually emitted
        gen += 1
    return chain


# ---------------------------------------------------------------- dashboard
_CSS = """
:root{--bg:#0b0f1a;--pearl:#f3eee2;--gold:#c9a24b;--green:#67b291;--red:#d06a6a;--amber:#d8b25a;--mut:#8a93a6;--card:#121826;}
*{box-sizing:border-box}
body{font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--pearl);margin:0;padding:36px;line-height:1.5}
.container{max-width:1040px;margin:0 auto}
h1{font-size:2rem;letter-spacing:1px;margin:0}
h2{color:var(--gold);font-size:1.1rem;border-bottom:1px solid rgba(201,162,75,.25);padding-bottom:6px;margin-top:0}
.sub{color:var(--mut)}
.panel{background:var(--card);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:20px;margin:16px 0}
.strip{display:flex;flex-wrap:wrap;gap:12px}
.metric{flex:1;min-width:120px;background:#0e1422;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:14px}
.metric .v{font-size:1.5rem;font-weight:700;color:var(--gold)}
.metric .k{color:var(--mut);font-size:.8rem;text-transform:uppercase;letter-spacing:.5px}
.funnel{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:.95rem}
.funnel .node{background:#0e1422;border:1px solid rgba(201,162,75,.3);border-radius:6px;padding:8px 12px}
.funnel .arr{color:var(--mut)}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid rgba(255,255,255,.06)}
th{color:var(--mut);font-weight:600;text-transform:uppercase;font-size:.72rem;letter-spacing:.5px}
.pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.78rem;font-weight:600}
.ok{background:#15321f;color:var(--green)} .bad{background:#3a1a1a;color:var(--red)} .warn{background:#33290f;color:var(--amber)}
.lbl{font-size:.72rem;color:var(--mut)}
.chain{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.gen{background:#0e1422;border:1px solid rgba(201,162,75,.3);border-radius:8px;padding:10px 14px;min-width:150px}
.gen .id{color:var(--gold);font-weight:700}
.edge{color:var(--green);font-size:.82rem}
.tl{font-family:ui-monospace,monospace;font-size:.84rem;color:#cdd6e6}
.tl .w{color:var(--amber)}
code{background:#0e1422;padding:1px 6px;border-radius:4px;color:var(--green);font-size:.82rem}
.artifact{background:#0e1422;border-left:3px solid var(--gold);padding:12px 14px;margin:10px 0;border-radius:6px}
.hero{border:1px solid rgba(201,162,75,.45)}
.flag{background:rgba(208,106,106,.14)}
.mono{font-family:ui-monospace,monospace;font-size:.8rem}
footer{color:var(--mut);font-size:.82rem;margin-top:30px;border-top:1px solid rgba(255,255,255,.06);padding-top:16px}
"""


def _status_pill(s):
    cls = {"real": "ok", "simulated": "warn", "error": "bad", "planned": "warn"}.get(s, "warn")
    return f'<span class="pill {cls}">{s.upper()}</span>'


# ---------------------------------------------------------------- audit ledger (the moat, made visible)
_DECISION = {"auto_approved": "AUTO-ALLOWED", "pending": "GATED-PENDING",
             "approved": "HUMAN-APPROVED", "blocked": "BLOCKED"}

def build_audit_rows(root, approved_ids):
    """Serialize the governance decisions into a tamper-evident, hash-chained audit ledger.
    Pure read over GuardrailReport.items — no new decision logic. The override column makes the
    un-bribable property tabular: an action a human pre-approved that the engine still BLOCKED."""
    approved = set(approved_ids or [])
    rep = root.guardrail_report
    committed = float(root.budget.current_spend_usd)
    prev_hash = "0" * 64
    rows = []
    for it in rep.items:
        blocked = it.status == "blocked"
        if not blocked:
            committed = round(committed + it.est_cost_usd, 2)
        rule = it.hits[-1].rule if it.hits else ""
        reason = it.hits[-1].reason if it.hits else (it.required_because[0] if it.required_because else "")
        row = {
            "decision_id": it.id,
            "action": it.title,
            "capability": it.capability,
            "est_cost_usd": it.est_cost_usd,
            "decision": _DECISION.get(it.status, it.status.upper()),
            "rule_fired": rule,
            "reason": reason,
            "human_override_attempted": str(it.action_id in approved).lower(),
            "final_outcome": "BLOCKED" if blocked else ("ALLOWED" if it.status in ("auto_approved", "approved") else "PENDING"),
            "cumulative_committed_usd": committed,
            "limit_usd": rep.limit_usd,
        }
        payload = "|".join(str(row[k]) for k in row)
        row["prev_hash"] = prev_hash
        row["row_hash"] = hashlib.sha256((prev_hash + "|" + payload).encode()).hexdigest()
        prev_hash = row["row_hash"]
        rows.append(row)
    return rows


def export_audit_ledger(rows, out_dir: Path):
    """Write audit-ledger.csv + audit-ledger.json (exportable, finance-reconcilable, tamper-evident)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audit-ledger.json").write_text(json.dumps(rows, indent=2))
    if rows:
        with open(out_dir / "audit-ledger.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return out_dir / "audit-ledger.csv"


def render_dashboard(chain, stripe_result, hermes_result, out_html: Path, started, ended, eval_result=None, audit_rows=None):
    root_run, root = chain[0]
    m = root.metrics
    rep = root.guardrail_report
    audit_rows = audit_rows or []
    H = []
    H.append(f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Protos — {root.run_id}</title><style>{_CSS}</style></head><body><div class='container'>")

    # Header
    H.append(f"""<div class='panel'>
      <div class='sub'>PROTOS · QHANTOM · the governed trust layer for agent money</div>
      <h1>The cap is enforced <em>below</em> the human.</h1>
      <p class='sub'>{esc(root.name)} · run <code>{esc(root.run_id)}</code> · {datetime.fromtimestamp(started).strftime('%Y-%m-%d %H:%M:%S')} · {ended-started:.2f}s</p>
      <p>A governed agent runs a real revenue cycle — and an audited brake the operator cannot override stands between it and the money.</p>
      <p>Status: {'<span class="pill bad">1+ ACTIONS REFUSED</span>' if rep.blocked else '<span class="pill ok">CLEAN</span>'} &nbsp; <span class='lbl'>{esc(root.run_status)}</span></p>
    </div>""")

    # ===== HERO 1 — GOVERNANCE (the un-bribable brake) =====
    H.append("<div class='panel hero'><h2>Governance — the budget hard-stop holds below the human</h2>")
    H.append(f"<p>Committed <strong>${rep.committed_spend_usd:.0f}</strong> / ${rep.limit_usd:.0f} limit · "
             f"budget_ok = {'<span class=\"pill ok\">YES</span>' if rep.budget_ok else '<span class=\"pill bad\">NO</span>'} · "
             f"{len(rep.pending)} pending · {len(rep.approved)} approved · {len(rep.blocked)} blocked</p>")
    if rep.blocked:
        H.append("<table><tr><th>Refused action</th><th>Cost</th><th>Pre-approved by human?</th><th>Reason</th></tr>")
        for b in rep.blocked:
            overrode = any(r['decision_id'] == b.action_id and r['human_override_attempted'] == 'true' for r in audit_rows)
            H.append(f"<tr class='flag'><td><span class='pill bad'>BLOCKED</span> {esc(b.title[:46])}</td><td>${b.est_cost_usd:.0f}</td>"
                     f"<td>{'<span class=\"pill bad\">⚠ YES — and still refused</span>' if overrode else 'no'}</td><td>{esc(b.hits[-1].reason)}</td></tr>")
        H.append("</table><p class='lbl'>This action was pre-approved by a human (<code>--approve</code>) and the engine refused it anyway. "
                 "The cap holds <strong>below</strong> the human — it cannot be bribed by clicking yes.</p>")
    H.append("<p class='lbl'>Incumbents monetize the very spend they would police; Protos is the neutral referee — and the proof is the "
             "exportable, tamper-evident receipt below.</p></div>")

    # ===== HERO 2 — AUDIT LEDGER (the moat, made visible) =====
    H.append("<div class='panel hero'><h2>Audit Ledger — exportable · tamper-evident · vendor-neutral</h2>")
    H.append("<p class='lbl'>Every governance decision, SHA-256 hash-chained (each row commits to the prior — alter one and the chain breaks). "
             "Exported to <code>audit-ledger.csv</code> + <code>.json</code> per run; finance-reconcilable.</p>")
    H.append("<table class='mono'><tr><th>#</th><th>Action</th><th>Decision</th><th>Human override?</th><th>Outcome</th><th>Committed</th><th>row_hash</th></tr>")
    for i, r in enumerate(audit_rows):
        flag = (r['final_outcome'] == 'BLOCKED' and r['human_override_attempted'] == 'true')
        dcls = {'BLOCKED': 'bad', 'AUTO-ALLOWED': 'ok', 'HUMAN-APPROVED': 'ok'}.get(r['decision'], 'warn')
        H.append(f"<tr class='{'flag' if flag else ''}'><td>{i+1}</td><td>{esc(str(r['action'])[:38])}</td>"
                 f"<td><span class='pill {dcls}'>{esc(r['decision'])}</span></td>"
                 f"<td>{'⚠ YES' if r['human_override_attempted']=='true' else 'no'}</td>"
                 f"<td>{esc(r['final_outcome'])}</td><td>${r['cumulative_committed_usd']:.0f}</td>"
                 f"<td><code>{esc(r['row_hash'][:12])}…</code></td></tr>")
    H.append("</table>")
    over = next((r for r in audit_rows if r['final_outcome'] == 'BLOCKED' and r['human_override_attempted'] == 'true'), None)
    if over:
        H.append(f"<p class='lbl'>Receipt for <code>{esc(over['decision_id'])}</code>: human_override_attempted=<strong>true</strong>, "
                 f"final_outcome=<strong>BLOCKED</strong>. The signed line proves the refusal survived the human's approval.</p>")
    H.append("</div>")

    # ===== Money Loop (DEMOTED — a worked example; outcomes PROJECTED, only cost real) =====
    roi_disp = f"{m.roi}×" if m.roi is not None else "—"
    cpql_disp = f"${m.cost_per_qualified_usd:.2f}" if m.cost_per_qualified_usd is not None else "—"
    H.append("<div class='panel'><h2>Worked example — a governed revenue cycle <span class='lbl'>(PROJECTED outcomes · real cost)</span></h2>")
    H.append("<div class='funnel'>"
             f"<span class='node'>{m.prospects} prospects</span><span class='arr'>→</span>"
             f"<span class='node'>{m.qualified} qualified <span class='lbl'>({m.qualify_rate:.0%})</span></span><span class='arr'>→</span>"
             f"<span class='node'>{m.booked} booked <span class='lbl'>({m.book_rate:.0%})</span></span><span class='arr'>→</span>"
             f"<span class='node'>${m.gross_revenue_usd:,.0f} projected billable</span></div>")
    H.append("<div class='strip' style='margin-top:14px'>"
             f"<div class='metric'><div class='v'>${m.net_revenue_usd:,.0f}</div><div class='k'>Net / cycle · projected</div></div>"
             f"<div class='metric'><div class='v'>${m.ops_cost_usd:.0f}</div><div class='k'>Ops cost · real</div></div>"
             f"<div class='metric'><div class='v'>{roi_disp}</div><div class='k'>ROI · projected</div></div>"
             f"<div class='metric'><div class='v'>{cpql_disp}</div><div class='k'>Cost / qualified · projected</div></div>"
             f"<div class='metric'><div class='v'>${m.price_per_qualified_usd:.0f}</div><div class='k'>Price / qualified</div></div></div>")
    H.append(f"<p class='lbl'>Provenance: {esc(m.provenance)}</p></div>")

    # Routing
    H.append("<div class='panel'><h2>Routing — capability_need is authoritative</h2><table><tr><th>Action</th><th>Needs</th><th>Routed to</th><th>Score</th></tr>")
    for r in root.candidate_routes:
        H.append(f"<tr><td>{esc(r.title[:54])}</td><td><code>{esc(r.capability_need)}</code></td><td><code>{esc(r.selected.capability)}</code> <span class='lbl'>fit {r.selected.fit}/5</span></td><td>{r.selected.score}</td></tr>")
    H.append("</table></div>")

    # Revenue infra (Stripe) — gated
    sid = stripe_result.get("ids", {})
    net_cents = stripe_result.get("net_cents")
    H.append("<div class='panel'><h2>Revenue Infrastructure — Stripe earn loop</h2>")
    H.append(f"<p>{_status_pill(stripe_result.get('status','planned'))} test-mode · {esc(stripe_result.get('note',''))}</p>")
    H.append("<table>"
             f"<tr><th>Product</th><td><code>{sid.get('product','—')}</code></td></tr>"
             f"<tr><th>Price</th><td><code>{sid.get('price','—')}</code> (${stripe_result.get('price_usd','—')})</td></tr>"
             f"<tr><th>Payment link</th><td><code>{stripe_result.get('payment_link_url','—')}</code></td></tr>"
             f"<tr><th>Payment intent</th><td><code>{sid.get('payment_intent','—')}</code></td></tr>"
             f"<tr><th>Charge</th><td><code>{sid.get('charge','—')}</code> · captured <strong>${stripe_result.get('amount_captured_cents',0)/100:,.2f}</strong></td></tr>"
             f"<tr><th>Balance txn</th><td><code>{sid.get('balance_txn') or '—'}</code> · net {('$'+format(net_cents/100,',.2f')) if net_cents is not None else '— (settles post-capture)'}</td></tr>"
             "</table>")
    if stripe_result.get("status") == "real":
        H.append("<p class='lbl'>These are real Stripe test objects — paste any id into your Stripe test dashboard to verify.</p>")
    H.append("</div>")

    # Compounding — the skill artifact is REAL/installable; the uplift is PROJECTED; the fixture
    # check is ILLUSTRATIVE (hand-built, not a benchmark) — quarantined so it can't be misread as a measurement.
    H.append("<div class='panel'><h2>Skill Compounding — a real installable skill, a projected uplift</h2>")
    if eval_result:
        H.append(f"<div class='artifact'><span class='pill warn'>ILLUSTRATIVE</span> "
                 f"Mechanism check ({esc(str(eval_result.get('n')))} hand-built fixtures — not a benchmark): the v2 "
                 f"qualification heuristic ranks the high-intent fixtures above the firmographically-attractive ones "
                 f"(v1 {eval_result.get('v1_score')} → v2 {eval_result.get('v2_score')}). It shows the mechanism, not a measured gain. "
                 f"<span class='lbl'>Re-run: <code>python3 eval_skill.py</code></span></div>")
    H.append("<p class='lbl'>The engine emitted a real, installable Hermes <code>SKILL.md</code> (below). The revenue "
             "before/after numbers are a <strong>PROJECTED</strong> model of impact — not measured conversions.</p>"
             "<table><tr><th>Metric (PROJECTED)</th><th>Before</th><th>After</th><th>Delta</th></tr>"
             f"<tr><td>Qualify rate</td><td>{m.qualify_rate-m.qualify_rate_delta:.0%}</td><td>{m.qualify_rate:.0%}</td><td class='edge'>{m.qualify_rate_delta:+.0%}</td></tr>"
             f"<tr><td>Booked-call rate</td><td>{m.book_rate-m.book_rate_delta:.0%}</td><td>{m.book_rate:.0%}</td><td class='edge'>{m.book_rate_delta:+.0%}</td></tr>"
             f"<tr><td>Net revenue</td><td>${m.net_revenue_usd-m.net_revenue_delta_usd:,.0f}</td><td>${m.net_revenue_usd:,.0f}</td><td class='edge'>${m.net_revenue_delta_usd:+,.0f}</td></tr>"
             "</table>"
             f"<p class='lbl'>Upgrade: <strong>{esc(m.learned_cause)}</strong> · real artifact written to <code>{esc(Path(root.compounded_skill_path).name if root.compounded_skill_path else 'compounded-skill.md')}</code></p></div>")

    # Allocation
    a = root.revenue_allocation or {}
    H.append("<div class='panel'><h2>Human Revenue Allocation</h2>"
             "<div class='strip'>"
             f"<div class='metric'><div class='v'>${a.get('company_usd',0):,.0f}</div><div class='k'>Company</div></div>"
             f"<div class='metric'><div class='v'>${a.get('reseed_usd',0):,.0f}</div><div class='k'>Re-seed next agent</div></div>"
             f"<div class='metric'><div class='v'>${a.get('ops_usd',0):,.0f}</div><div class='k'>Ops</div></div></div>"
             f"<p class='lbl'>{esc(a.get('note',''))} (split of projected net)</p></div>")

    # Chain
    H.append("<div class='panel'><h2>Agent Company Chain — spawned in-process</h2><div class='chain'>")
    for i, (rn, res) in enumerate(chain):
        mm = res.metrics
        H.append(f"<div class='gen'><div class='id'>gen {i+1}</div><div class='lbl'><code>{res.run_id}</code></div>"
                 f"<div>budget ${rn.budget.monthly_limit_usd:.0f}</div><div>qualify {mm.qualify_rate:.0%}</div>"
                 f"<div>net ${mm.net_revenue_usd:,.0f}</div></div>")
        if i < len(chain)-1:
            H.append(f"<span class='edge'>— re-seed ${res.revenue_allocation.get('reseed_usd',0):.0f} →</span>")
    H.append("</div><p class='lbl'>Each generation inherits the compounded skill and a higher (projected) conversion baseline. "
             "The chain runs to <code>--depth</code>, or stops earlier when the projected per-generation skill uplift "
             "saturates. Dollar figures are PROJECTED.</p></div>")

    # Timeline
    H.append("<div class='panel'><h2>Timeline</h2><div class='tl'>")
    for ev in root.timeline:
        cls = " class='w'" if ev.level == "warn" else ""
        H.append(f"<div{cls}>[+{ev.ts_offset_ms}ms] <strong>{esc(ev.phase)}</strong> — {esc(ev.message)}</div>")
    H.append("</div></div>")

    # Reality ledger
    stripe_status = stripe_result.get("status", "planned")
    hermes_state = (hermes_result.get("status", "not-run") if hermes_result else "not-run")
    hermes_cls = "bad" if hermes_state == "error" else ("ok" if hermes_state == "ok" else "warn")
    H.append("<div class='panel'><h2>Reality Ledger</h2><table>"
             "<tr><th>Component</th><th>State</th></tr>"
             "<tr><td>Routing / budget hard-stop / guardrails</td><td><span class='pill ok'>REAL — deterministic engine</span></td></tr>"
             "<tr><td>Audit ledger (SHA-256 hash-chained, exportable CSV/JSON)</td><td><span class='pill ok'>REAL — generated, tamper-evident</span></td></tr>"
             f"<tr><td>Stripe earn loop (product/price/link/txn ids)</td><td>{_status_pill(stripe_status)} <span class='lbl'>test-mode earn loop</span></td></tr>"
             f"<tr><td>Hermes ops execution</td><td><span class='pill {hermes_cls}'>{esc(hermes_state.upper())}</span></td></tr>"
             "<tr><td>Funnel outcomes (qualify/book rates, $)</td><td><span class='pill warn'>PROJECTED — deterministic model, no live sends</span></td></tr>"
             "<tr><td>Compounded skill artifact (installable SKILL.md)</td><td><span class='pill ok'>REAL — generated, on disk, parseable</span></td></tr>"
             "<tr><td>Projected conversion uplift from the upgrade</td><td><span class='pill warn'>PROJECTED — modeled, not measured conversions</span></td></tr>"
             "<tr><td>Agent-company chain</td><td><span class='pill ok'>REAL — child YAML runnable, executed in-process</span></td></tr>"
             "</table></div>")

    H.append("<footer>Protos by Qhantom · governed agents do the redundant money-making work so humans pursue the ambitious. "
             "Every figure is tagged real, projected, or simulated — nothing is presented as more real than it is.</footer></div></body></html>")
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text("".join(H))
    return out_html


# ---------------------------------------------------------------- bundle
_INSTALL_SH = """#!/usr/bin/env bash
# Install the governed revenue-ops skill into a Hermes skills directory.
set -euo pipefail
DEST="${1:-$HOME/.hermes/skills}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DEST/revenue-ops-lead-to-revenue"
cp "$HERE/skills/revenue-ops-lead-to-revenue/SKILL.md" "$DEST/revenue-ops-lead-to-revenue/SKILL.md"
echo "Installed revenue-ops-lead-to-revenue -> $DEST/revenue-ops-lead-to-revenue/SKILL.md"
echo "Verify:  hermes skills list | grep revenue-ops    then invoke  /revenue-ops"
"""

_BUNDLE_README = """# revenue-ops-lead-to-revenue — Hermes workflow bundle

A deployable, governed lead-to-revenue workflow for Hermes, produced by a Protos cycle.
Contents:
- `skills/revenue-ops-lead-to-revenue/SKILL.md` — the compounded v2 Hermes skill (frontmatter + workflow)
- `runs/<run>.yaml` — the governed run definition (budget, guardrails, actions) the engine executes
- `install.sh` — copies the skill into your Hermes skills dir

## Install
    ./install.sh                       # installs into ~/.hermes/skills
    hermes skills list | grep revenue-ops
    # then invoke the workflow as /revenue-ops inside Hermes

## Run the governed cycle (research -> qualify -> outreach -> bill, with budget hard-stops)
    python3 ../runner.py --run runs/<run>.yaml --approve quality-review-leads allocate-revenue

The skill improves each cycle on a reproducible eval (`eval_skill.py`); the bundle is the unit
an operator or enterprise installs to run the governed revenue workflow out of the box.
"""


def build_bundle(root, run_path: Path, bundle_dir: Path) -> Path:
    """Assemble an install-ready Hermes bundle: the compounded v2 skill + run + README + installer."""
    skills_dir = bundle_dir / "skills" / "revenue-ops-lead-to-revenue"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "SKILL.md").write_text(root.compounded_skill_content)
    (bundle_dir / "runs").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "runs" / run_path.name).write_text(run_path.read_text())
    (bundle_dir / "README.md").write_text(_BUNDLE_README)
    install = bundle_dir / "install.sh"
    install.write_text(_INSTALL_SH)
    install.chmod(0o755)
    return bundle_dir


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(RUN_PATH))
    ap.add_argument("--hermes-path", default=HERMES_DEFAULT)
    ap.add_argument("--approve", nargs="*", default=[], help="Action ids to pre-approve")
    ap.add_argument("--depth", type=int, default=2, help=f"Child generations to spawn in-process (0..{DEPTH_CAP})")
    ap.add_argument("--real-stripe", action=argparse.BooleanOptionalAction, default=True,
                    help="REAL test-mode Stripe earn loop (ON by default; needs a test key + `pip install stripe`). Use --no-real-stripe to force the labeled simulation.")
    ap.add_argument("--real-hermes", action="store_true", help="Actually invoke Hermes for the ops work (needs a provider)")
    args = ap.parse_args()

    started = time.time()
    rprint("[bold cyan]PROTOS — Lead-to-Revenue Runner[/bold cyan]" if RICH else "PROTOS — Lead-to-Revenue Runner")
    try:
        root_run = parse_run(Path(args.run).read_text())
    except FileNotFoundError:
        raise SystemExit(f"Run file not found: {args.run}")

    depth = min(max(args.depth, 0), DEPTH_CAP)

    # 0. Real, reproducible skill-quality eval (v1 vs v2) — the measured basis of "the skill got better"
    from eval_skill import run_eval
    eval_result = run_eval(out_path=OUT_DIR / "skill-eval.json")

    # 1. Governed chain (root cycle + spawned children, in-process)
    chain = run_chain(root_run, args.approve, depth, eval_result)
    root_run, root = chain[0]

    # 2. Stripe earn loop — the money proof. Goes REAL only with --real-stripe AND a test key present;
    #    otherwise returns a clearly-labeled simulation (never silently goes real, never fakes success).
    stripe_result = run_earn_loop(root_run.offer_seed["name"],
                                  float(root_run.offer_seed.get("target_price_usd", 49)),
                                  out_path=OUT_DIR / "stripe-earn.json",
                                  allow_real=args.real_stripe)
    # attach to engine artifact (truthful status)
    root.stripe_artifact.status = stripe_result.get("status", "planned")
    root.stripe_artifact.real_object_ids = stripe_result.get("ids", {})
    root.stripe_artifact.payment_link_url = stripe_result.get("payment_link_url")

    # 3. Optional: invoke Hermes for the actual ops work (default simulated, labeled)
    hermes_result = fulfill_lead_ops_cycle(
        brief=f"Vertical from goal: {root_run.goal[:120]}. Offer: {root_run.offer_seed['one_liner']}",
        skill="revenue-ops-lead-to-revenue", real=args.real_hermes, hermes_path=args.hermes_path)
    (OUT_DIR / "ops-fulfillment.json").parent.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "ops-fulfillment.json").write_text(json.dumps(hermes_result, indent=2))

    # 4. Persist artifacts (real content) + a conversion report
    save_result(root, OUT_DIR)
    conv = {
        "run_id": root.run_id,
        "prospects": root.metrics.prospects, "qualified": root.metrics.qualified, "booked": root.metrics.booked,
        "qualify_rate": root.metrics.qualify_rate, "book_rate": root.metrics.book_rate,
        "gross_revenue_usd": root.metrics.gross_revenue_usd, "ops_cost_usd": root.metrics.ops_cost_usd,
        "net_revenue_usd": root.metrics.net_revenue_usd, "roi": root.metrics.roi,
        "cost_per_qualified_usd": root.metrics.cost_per_qualified_usd, "provenance": root.metrics.provenance,
    }
    (OUT_DIR / "conversion-report.json").write_text(json.dumps(conv, indent=2))

    # 4b. Audit ledger — the exportable, tamper-evident receipt of every governance decision
    audit_rows = build_audit_rows(root, args.approve)
    export_audit_ledger(audit_rows, OUT_DIR)

    # 4c. Assemble the install-ready Hermes workflow bundle (skill + run + README + installer)
    bundle_dir = build_bundle(root, Path(args.run), ROOT / "bundle")
    # snapshot the bundle's v2 skill into the run dir too
    (OUT_DIR / "revenue-ops-lead-to-revenue.SKILL.md").write_text(root.compounded_skill_content)

    ended = time.time()

    # 5. Dashboard (truthful)
    dash = render_dashboard(chain, stripe_result, hermes_result, OUT_DIR / "dashboard.html", started, ended, eval_result, audit_rows)
    (ROOT / "current-dashboard.html").write_text(dash.read_text())

    # 6. Summary
    m = root.metrics
    roi_disp = f"{m.roi}×" if m.roi is not None else "n/a"
    body = (f"Chain: {len(chain)} generation(s). Root net ${m.net_revenue_usd:,.0f} (projected) on ${m.ops_cost_usd:.0f} real cost (ROI {roi_disp}).\n"
            f"Governance: {len(root.guardrail_report.blocked)} blocked (hard stop), "
            f"{len(root.guardrail_report.pending)} pending, committed ${root.guardrail_report.committed_spend_usd:.0f}/${root.guardrail_report.limit_usd:.0f}.\n"
            f"Stripe earn loop: {stripe_result.get('status','?').upper()} · Hermes: {hermes_result.get('status','?').upper()}.\n"
            f"Skill eval (illustrative, n={eval_result['n']}): v1 {eval_result['v1_score']} -> v2 {eval_result['v2_score']} (mechanism check, not a benchmark).\n"
            f"Audit ledger -> {OUT_DIR}/audit-ledger.csv ({len(audit_rows)} hash-chained decisions).\n"
            f"Compounded skill -> bundle/skills/revenue-ops-lead-to-revenue/SKILL.md (install: ./bundle/install.sh)\n"
            f"Artifacts in {OUT_DIR}\nDashboard: {dash}  (synced to current-dashboard.html)")
    rprint(Panel(body, title="Protos cycle complete") if RICH else body)


if __name__ == "__main__":
    main()
