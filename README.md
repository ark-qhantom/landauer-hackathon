# Landauer — Runtime Constitution for the Agent Economy

*Pre-execution guardrails for Hermes agents that spend, earn, compute, use credentials, and touch the real world.*

**Landauer is the authority layer for autonomous agents.** It gates every action a Hermes agent proposes
— **spend, earnings, compute, energy, credentials, and public/irreversible actions** — against a
human-defined constitution **before execution**, then records every decision as an auditable receipt.

As agents move from assistants to operators, they will increasingly spend, earn, consume compute, use
credentials, and create public outcomes for companies and individuals. Landauer is built for that
transition: a runtime constitution that gives agents authority inside enforceable limits, with receipts
for every decision. **Agent capability is becoming abundant; agent authority is the bottleneck.**

> **The cap is enforced *below* the human.** A human may approve an action, but approval cannot lift a
> hard resource cap unless the constitution explicitly grants override. One click of *yes* cannot bribe a
> dollar or a joule limit.

- **Humans** define the operating envelope — the constitution.
- **Hermes agents** do the work — they propose the actions.
- **Landauer** governs that authority *before actions reach the real world*, writing a receipt for every
  **allow / block / escalate** decision.

*Named for Landauer's principle — that computation has an irreducible physical energy cost. Landauer
makes that cost, and its dollar and permission counterparts, a first-class, enforceable policy limit.*

## Demo

- X demo post: https://x.com/ark_qhantom/status/2072135934527541432
- Built for: Hermes Agent Accelerated Business Hackathon

---

## The problem

AI agents are moving from *generating text* to *taking action*: earning and spending money, using
credentials, consuming GPU compute, and creating public outcomes. The controls we have are weak — asking
a human every time doesn't scale, prompt-level safety isn't enforcement, and API/GPU spend is easy to
blow up via runaway loops and retries before anyone sees the bill.

Landauer is the authority layer between the agent and the world: **autonomous enough to be useful,
bounded enough to be trusted.** Dollars are economic limits, permissions are institutional limits,
**joules are physical limits** — enforced *before execution*, not observed after the fact. Humans define
the envelope once; agents operate autonomously within it; every action leaves a receipt.

The agent can still draft, reason, and prepare work. Landauer only gates the final external or
irreversible step when policy requires review.

---

## What Landauer enforces

Every decision — allow, block, *and* escalate — is checked *before execution* and written as a receipt.

| Governed dimension | Example action | Landauer's decision |
|---|---|---|
| **Spend cap** | agent spends **$42** on an API model (cap $500) | **ALLOW** → real Stripe test charge (`pi_…`), receipt written |
| **Spend cap** | agent tries to spend **$4,800** (> $500) | **BLOCK** *before* the charge — `usd_cap_exceeded`, no money moves |
| **Energy cap** | real GPU job, **520 J** measured (cap 1,000 J) | **ALLOW** — real `nvidia-smi` ∫P·dt, under cap |
| **Energy cap, below the human** | **human-approved** GPU job, ~18,000 J projected | **BLOCK** — `joule_cap_exceeded` *despite* approval |
| **Credential scope** | agent tries to export customer PII | **BLOCK** — `credential_scope_denied` (scope not granted) |
| **Public / irreversible** | agent wants to post publicly | **ESCALATE** — routed to a human |

Most actions are auto-decided by policy; a human is pulled in only on `escalate`. That is the point:
**scale agent authority without scaling human supervision linearly.**

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

Every decision is written to a generated JSONL ledger at `ledger/landauer_events.jsonl`. Example receipts
are included in [`submission-artifacts/real-run-4070/`](submission-artifacts/real-run-4070/).

```
timestamp · receipt_id · agent_id · policy_version · action · human_approved ·
usd_estimate · usd_cap · joules_estimate · joules_cap · runtime_seconds ·
decision · reason · stripe_object_id? · nvidia_telemetry?
```

Reason codes: `within_policy`, `human_approval_missing`, `usd_cap_exceeded`, `joule_cap_exceeded`,
`runtime_cap_exceeded`, `credential_scope_denied`, `public_action_requires_review`, `action_not_allowed`.

---

## Integrations — real, before execution

Landauer checks each proposed action *before it reaches the real world*, using real signals from each system.

**Hermes** ([`landauer/adapters/hermes.py`](landauer/adapters/hermes.py))
- Hermes agents propose the actions.
- Landauer checks those actions before execution.
- A tight, single-shot call asks Hermes for the next action as strict JSON; a clearly-labeled
  deterministic fallback covers inference errors — we never report a success we didn't get.

**Stripe** ([`landauer/adapters/stripe_budget.py`](landauer/adapters/stripe_budget.py))
- Stripe accounts for agent spend.
- Landauer decides whether that spend is allowed.
- The demo uses Stripe **test-mode spend proof**: an allowed spend creates a real `PaymentIntent`
  (`pi_…`), a blocked spend never reaches Stripe. No live key is ever used.

**NVIDIA** ([`landauer/adapters/nvidia.py`](landauer/adapters/nvidia.py))
- NVIDIA telemetry is not just powering inference.
- NVIDIA telemetry becomes **evidence inside the policy decision**.
- The demo uses `nvidia-smi` power/runtime readings to **measure or project joules** (∫P·dt over live
  samples), so the energy cap is enforced on real physics — not a guess.

---

## Where it fits

Companies don't want agents that ask permission for every tiny action, and they cannot accept agents that
act without limits. Landauer is the authority layer: humans define policy once, agents operate
autonomously within it, and every action receives a receipt showing the policy version, approval state,
dollar cost, compute/energy use, and final decision — decided *before* the action runs.

**Concrete use cases — each maps to something the demo actually enforces:**
- a **support agent capped at $X per ticket** — overspend blocked *before* the API call
- an **earning/ops agent** metered on real Stripe test-mode spend, allowed only within its budget
- a **data-pipeline agent that cannot export customer PII** without an approved credential scope (`export_customer_data` → `credential_scope_denied`)
- an **outbound/social agent** whose public posts are routed to a human (`public_post` → `escalate`)
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
side effects only after an `allowed` decision, so the gate stays deterministic, pre-execution, and
unit-testable.

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

> **Humans set the rules. Hermes agents do the work. Landauer leaves the receipt.**

<sub>Built for the Hermes Agent Accelerated Business Hackathon. Validated on an RTX 4070 Ti SUPER with real `nvidia-smi` telemetry.</sub>
