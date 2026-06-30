# Landauer — a runtime constitution for autonomous agents

**Nous × NVIDIA hackathon.** Landauer is a runtime constitution for autonomous agents. It gates agent
actions through human-defined policy for **spend, compute, energy, credentials, and approvals before
execution**, then records every decision as an auditable receipt.

This demo shows a **Hermes** agent attempting API and local-compute tasks. Landauer checks
**Stripe**-backed budget policy and **NVIDIA**-backed GPU telemetry before allowing or blocking each
action, and writes every decision to a durable ledger.

> **Hermes decides what to do, NVIDIA tells us what compute it costs, Stripe accounts for what it
> spends, and Landauer decides whether the action is allowed.**

| System | Role |
|---|---|
| **Hermes** | agent runtime — proposes the action |
| **NVIDIA** | GPU telemetry — power, runtime, joules (∫P·dt, real `nvidia-smi`) |
| **Stripe** | treasury — budget + real test-mode spend |
| **Landauer** | policy engine — allow / block / escalate, then write the receipt |

*Named for Landauer's principle — that computation has a real, physical energy cost — Landauer makes that
cost (and its dollar and permission counterparts) a first-class, enforceable policy limit.*

---

## Why this matters

AI agents are moving from *generating text* to *taking action*: calling APIs, spending money, using
credentials, and consuming local GPU resources. Current controls are weak — asking a human every time
doesn't scale, prompt-level safety isn't enforcement, and API/GPU spend is easy to blow up via runaway
loops and retries before anyone sees the bill.

Landauer is the middle layer: **autonomous enough to be useful, bounded enough to be trusted.** Dollars
are economic limits, permissions are institutional limits, **joules are physical limits** — together
they make Landauer stronger than a spend-management or logging tool. The headline property:

> **The cap is enforced *below* the human.** A human may approve an action, but approval cannot lift a
> hard resource cap unless the constitution explicitly grants override. One click of *yes* cannot bribe
> a dollar or joule limit.

---

## Run the demo

```bash
# real Stripe test charge + real Hermes proposal + real GPU joules:
python demo/run_landauer_demo.py

# offline / no GPU / no keys (still 100% real decision logic):
python demo/run_landauer_demo.py --no-real-stripe --no-real-hermes --mock-nvidia --gpu-seconds 6

python demo/show_ledger.py        # the Reality Ledger (all receipts)
python test_landauer.py           # boring, judge-friendly PASS/FAIL of the core
```

> Requires **Python ≥ 3.12**; run with any `python` / `py -3` on PATH (the demo sets its own UTF-8 stdout).
> For the real-Hermes path, set `HERMES_PATH` to your `hermes` binary, or pass `--no-real-hermes`.

The constitution lives in [`config/demo_policy.yaml`](config/demo_policy.yaml) — human-readable, versioned:

```yaml
agent_id: hermes-demo-agent
policy_version: landauer-demo-v1
limits:
  max_usd_per_task: 1.00       # economic limit  (Stripe-backed)
  max_joules_per_task: 5000    # physical limit  (NVIDIA-backed, ∫P·dt)
  max_runtime_seconds: 120
approvals:
  human_required: true
  human_can_override_usd: false
  human_can_override_joules: false
```

## What each scenario proves

| Scenario | Action | Proves |
|---|---|---|
| **A** | `call_api_model` (under cap) | Hermes proposes → Landauer **ALLOWS** → **real Stripe** test charge (`pi_…`), receipt written |
| **B** | `call_api_model` ($1.40 > $1.00) | overspend **BLOCKED before execution** — `usd_cap_exceeded`, no charge made |
| **C** | `run_local_model` (real GPU) | **real NVIDIA telemetry** — measured `∫P·dt` joules under cap → **ALLOWED** |
| **D** | `large_gpu_job` (human-approved) | **the cap is enforced below the human** — `joule_cap_exceeded` despite approval |
| **Montage** | summarize / api / local / public / export / gpu | **policy-defined autonomy** — most actions auto-decided; humans pulled in only on `escalate` |

## How each sponsor is used (real, not mocked)

- **Hermes** ([`landauer/adapters/hermes.py`](landauer/adapters/hermes.py)) — a tight, single-shot call
  (no skill-loading) asks Hermes to propose the next action as strict JSON. Deterministic labeled
  fallback if inference errors; we never report a success we didn't get.
- **NVIDIA** ([`landauer/adapters/nvidia.py`](landauer/adapters/nvidia.py)) — wraps `telemetry.py`'s
  `NvidiaSmiProvider` + `EnergyMeter`; **measures** real joules (∫P·dt over live `nvidia-smi` samples)
  and **projects** joules (E ≈ P·t) for the pre-execution gate. A real `torch` GPU load
  ([`gpu_workload.py`](landauer/adapters/gpu_workload.py)) makes the numbers meaningful (~245 W on a 4070 Ti SUPER).
- **Stripe** ([`landauer/adapters/stripe_budget.py`](landauer/adapters/stripe_budget.py)) — a
  test-mode treasury; an **allowed** spend creates a real `PaymentIntent` (real `pi_/ch_` id), a
  **blocked** spend never reaches Stripe. No live key is ever used.

## What the ledger records

Every decision — allowed, blocked, *and* escalated — is one JSONL receipt in
[`ledger/landauer_events.jsonl`](ledger/landauer_events.jsonl):

```
timestamp · receipt_id · agent_id · policy_version · action · human_approved ·
usd_estimate · usd_cap · joules_estimate · joules_cap · runtime_seconds ·
decision · reason · stripe_object_id? · nvidia_telemetry?
```

Reason codes: `within_policy`, `human_approval_missing`, `usd_cap_exceeded`, `joule_cap_exceeded`,
`runtime_cap_exceeded`, `credential_scope_denied`, `public_action_requires_review`, `action_not_allowed`.

## Enterprise value

Companies don't want agents that ask permission for every tiny action, and they cannot accept agents
that act without limits. Landauer provides the middle layer: **humans define policy once, agents
operate autonomously within it, and every action receives a receipt** showing the policy version,
approval state, dollar cost, compute/energy use, and final decision. Landauer lets companies scale
agent labor without scaling human supervision linearly.

**Concrete use cases — each maps to a scenario the demo proves:**
- a **support agent capped at $X per ticket** — overspend blocked *before* the API call (Scenario A/B)
- a **data-pipeline agent that cannot export customer PII** without an approved credential scope (`export_customer_data` → `credential_scope_denied`)
- an **outbound/social agent** whose public posts are always routed to a human (`public_post` → `escalate`)
- a **local-inference fleet** with a hard per-job joule budget, enforced *below* the operator who approved it (Scenario D)

---

## Code map (Landauer core)

```
config/demo_policy.yaml        the human-readable runtime constitution
landauer/
  policy.py                    load + validate the constitution
  decision.py                  the pure gate: ActionRequest -> Decision + reason codes
  ledger.py                    the Reality Ledger (append-only JSONL receipts)
  adapters/
    nvidia.py                  real GPU telemetry (∫P·dt) + joule projection  (wraps telemetry.py)
    stripe_budget.py           Stripe-backed treasury, real test-mode spend   (wraps stripe_earn.py)
    gpu_workload.py            real torch/CUDA load so joules are meaningful
    hermes.py                  tight, no-skill Hermes action proposer
demo/
  run_landauer_demo.py         the five scenarios, clean panels
  show_ledger.py               pretty-print the ledger
test_landauer.py               core verifier (no GPU/Stripe/Hermes needed)
```

The decision kernel (`landauer/decision.py`) performs **no I/O** — adapters supply estimates and
execute side effects only after an `allowed` decision, so the gate stays deterministic and unit-testable.

---

## Energy-grounded governance engine (foundation)

Landauer's policy core is built on a validated physics-measurement layer and a hash-chained governance
engine (the original energy-budget work, retained as the measurement substrate the NVIDIA adapter wraps).
*`protos_core.py` / `runner.py` are internal/legacy module names for this substrate — not a separate product.*

- `telemetry.py` — `NvidiaSmiProvider` (REAL `nvidia-smi`) + deterministic `FallbackSimulator` (MODELED) + `EnergyMeter` (∫P·dt). **Validated on an RTX 4070 Ti SUPER** — see [`4070-CAPTURE.md`](4070-CAPTURE.md).
- `protos_core.py` / `runner.py` — the energy-budget governance engine + SHA-256 hash-chained audit ledger + dashboard.
- `physics_task.py` — pure-stdlib velocity-Verlet solver with conservation checks (real metered work).
- `eval_skill.py` / `test_caps.py` — engine verification (dual caps survive `--approve`, energy inside the hash chain).

Every figure is tagged **real**, **modeled**, **theoretical**, or **dry-run** — nothing is presented as
more real than it is.

---

> **Humans set the rules. Agents do the work. Landauer leaves the receipt.**
