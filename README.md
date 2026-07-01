# Landauer — a runtime constitution for autonomous agents

*Runtime governance for autonomous agents · built for the Nous × NVIDIA hackathon*

**Landauer is the governance layer that sits between an autonomous agent and the world.** It gates every
action an agent proposes — **spend, compute, energy, credentials, and public/irreversible actions** —
against a human-defined policy *before* execution, then records every decision as an auditable receipt.

> **The cap is enforced *below* the human.** A human may approve an action, but approval cannot lift a
> hard resource cap unless the constitution explicitly grants override. One click of *yes* cannot bribe a
> dollar or a joule limit.

Landauer runs a **Hermes** agent against real work. **Stripe** backs the budget, **NVIDIA** measures the
compute, and Landauer decides — allow, block, or escalate — and writes the receipt.

| System | Role in Landauer |
|---|---|
| **Hermes** | agent runtime — proposes the action |
| **NVIDIA** | GPU telemetry — real power, runtime, joules (∫P·dt via `nvidia-smi`) |
| **Stripe** | treasury — budget + real test-mode spend |
| **Landauer** | policy engine — allow / block / escalate, then write the receipt |

*Named for Landauer's principle — that computation has an irreducible physical energy cost. Landauer
makes that cost, and its dollar and permission counterparts, a first-class, enforceable policy limit.*

---

## The problem

AI agents are moving from *generating text* to *taking action*: calling APIs, spending money, using
credentials, and consuming GPU resources. The controls we have are weak — asking a human every time
doesn't scale, prompt-level safety isn't enforcement, and API/GPU spend is easy to blow up via runaway
loops and retries before anyone sees the bill.

Landauer is the middle layer: **autonomous enough to be useful, bounded enough to be trusted.** Dollars
are economic limits, permissions are institutional limits, **joules are physical limits** — together they
make Landauer more than a spend-management or logging tool. Humans define the policy once; agents operate
autonomously within it; every action leaves a receipt.

---

## What Landauer enforces

Every decision — allow, block, *and* escalate — is written to the ledger as a receipt.

| Governed dimension | Example action | Landauer's decision |
|---|---|---|
| **Spend cap** | agent spends **$42** on an API model (cap $500) | **ALLOW** → real Stripe test charge (`pi_…`), receipt written |
| **Spend cap** | agent tries to spend **$4,800** (> $500) | **BLOCK** *before* execution — `usd_cap_exceeded`, no charge made |
| **Energy cap** | real GPU job, **520 J** measured (cap 1,000 J) | **ALLOW** — real `nvidia-smi` ∫P·dt, under cap |
| **Energy cap, below the human** | **human-approved** GPU job, ~18,000 J projected | **BLOCK** — `joule_cap_exceeded` *despite* approval |
| **Credential scope** | agent tries to export customer PII | **BLOCK** — `credential_scope_denied` (scope not granted) |
| **Public / irreversible** | agent wants to post publicly | **ESCALATE** — routed to a human |

Most actions are auto-decided by policy; a human is pulled in only on `escalate`. That is the point:
**scale agent labor without scaling human supervision linearly.**

---

## Run it

```bash
# real Stripe test charge + real Hermes proposal + real GPU joules:
python demo/run_landauer_demo.py

# cinematic, recordable presentation mode:
python demo/run_landauer_demo.py --presentation

# offline — no GPU, no keys, still 100% real decision logic:
python demo/run_landauer_demo.py --no-real-stripe --no-real-hermes --mock-nvidia

python demo/show_ledger.py        # the Reality Ledger — every receipt
python test_landauer.py           # fast to verify — PASS/FAIL of the core
```

> Requires **Python ≥ 3.12**; run with any `python` / `py -3` on PATH (the demo sets its own UTF-8 stdout).
> For the real-Hermes path, set `HERMES_PATH` to your `hermes` binary, or pass `--no-real-hermes`.

The constitution lives in [`config/demo_policy.yaml`](config/demo_policy.yaml) — human-readable, versioned:

```yaml
agent_id: hermes-demo-agent
policy_version: landauer-demo-v1
treasury:
  currency: usd
  budget_usd: 500.00
limits:
  max_usd_per_task: 500.00       # economic limit  (Stripe-backed)
  max_joules_per_task: 1000      # physical limit  (NVIDIA-backed, ∫P·dt)
  max_runtime_seconds: 30        # wall-clock limit
approvals:
  human_required: true
  human_can_override_usd: false
  human_can_override_joules: false
credentials:
  allowed_scopes:
    - stripe:test_payment_intents:create
    - nvidia:telemetry:read
    - hermes:proposal:request
```

---

## The receipt

Every decision — allowed, blocked, *and* escalated — is one JSONL receipt in
[`ledger/landauer_events.jsonl`](ledger/landauer_events.jsonl):

```
timestamp · receipt_id · agent_id · policy_version · action · human_approved ·
usd_estimate · usd_cap · joules_estimate · joules_cap · runtime_seconds ·
decision · reason · stripe_object_id? · nvidia_telemetry?
```

Reason codes: `within_policy`, `human_approval_missing`, `usd_cap_exceeded`, `joule_cap_exceeded`,
`runtime_cap_exceeded`, `credential_scope_denied`, `public_action_requires_review`, `action_not_allowed`.

---

## Integrations — real, not mocked

- **Hermes** ([`landauer/adapters/hermes.py`](landauer/adapters/hermes.py)) — a tight, single-shot call
  (no skill-loading) asks Hermes to propose the next action as strict JSON. Deterministic, clearly
  labeled fallback if inference errors; we never report a success we didn't get.
- **NVIDIA** ([`landauer/adapters/nvidia.py`](landauer/adapters/nvidia.py)) — wraps `telemetry.py`'s
  `NvidiaSmiProvider` + `EnergyMeter`; **measures** real joules (∫P·dt over live `nvidia-smi` samples)
  and **projects** joules (E ≈ P·t) for the pre-execution gate. A real `torch` GPU load
  ([`gpu_workload.py`](landauer/adapters/gpu_workload.py)) makes the numbers meaningful — real measured
  wattage on an RTX 4070 Ti SUPER (see [`4070-CAPTURE.md`](4070-CAPTURE.md)).
- **Stripe** ([`landauer/adapters/stripe_budget.py`](landauer/adapters/stripe_budget.py)) — a test-mode
  treasury; an **allowed** spend creates a real `PaymentIntent` (real `pi_/ch_` id), a **blocked** spend
  never reaches Stripe. No live key is ever used.

---

## Where it fits

Companies don't want agents that ask permission for every tiny action, and they cannot accept agents that
act without limits. Landauer is the middle layer: humans define policy once, agents operate autonomously
within it, and every action receives a receipt showing the policy version, approval state, dollar cost,
compute/energy use, and final decision.

**Concrete use cases — each maps to something the demo actually enforces:**
- a **support agent capped at $X per ticket** — overspend blocked *before* the API call
- a **data-pipeline agent that cannot export customer PII** without an approved credential scope (`export_customer_data` → `credential_scope_denied`)
- an **outbound/social agent** whose public posts are always routed to a human (`public_post` → `escalate`)
- a **local-inference fleet** with a hard per-job joule budget, enforced *below* the operator who approved it

---

## Architecture

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
  run_landauer_demo.py         the governed scenarios, clean panels
  show_ledger.py               pretty-print the ledger
test_landauer.py               core verifier (no GPU/Stripe/Hermes needed)
```

The decision kernel (`landauer/decision.py`) performs **no I/O** — adapters supply estimates and execute
side effects only after an `allowed` decision, so the gate stays deterministic and unit-testable.

---

## Foundation — the energy-measurement substrate

Landauer's policy core is built on a validated physics-measurement layer and a hash-chained governance
engine (the original energy-budget work, retained as the measurement substrate the NVIDIA adapter wraps).

- `telemetry.py` — `NvidiaSmiProvider` (REAL `nvidia-smi`) + deterministic `FallbackSimulator` (MODELED) + `EnergyMeter` (∫P·dt). **Validated on an RTX 4070 Ti SUPER** — see [`4070-CAPTURE.md`](4070-CAPTURE.md).
- `protos_core.py` / `runner.py` — the energy-budget governance engine + SHA-256 hash-chained audit ledger + dashboard. *(Internal/legacy module names for this substrate — not a separate product.)*
- `physics_task.py` — pure-stdlib velocity-Verlet solver with conservation checks (real metered work).
- `eval_skill.py` / `test_caps.py` — engine verification (dual caps survive `--approve`, energy inside the hash chain).

Every figure is tagged **real**, **modeled**, **theoretical**, or **dry-run** — nothing is presented as
more real than it is.

---

> **Humans set the rules. Agents do the work. Landauer leaves the receipt.**

<sub>Built for the Nous × NVIDIA hackathon · RTX AI Garage. Validated on an RTX 4070 Ti SUPER.</sub>
