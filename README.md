# Landauer — *agents that cannot outrun reality*

**Physics-grounded agent treasury framework** for the Hermes Agent Accelerated Business Hackathon
(Nous Research × NVIDIA × Stripe). A governed runtime where **every action has a reality label, a
hash-chained receipt, and an energy budget it cannot lie about.**

If agents are going to act in the world, what keeps them honest? Four constraints:

1. **Reality labels** — every action / number is `REAL`, `MODELED`, `THEORETICAL`, or `DRY-RUN` (and decisions are `AUTO-ALLOWED / PENDING / HUMAN-APPROVED / BLOCKED`).
2. **Capability gates** — the agent cannot spend / mutate / call real systems until a human approves (soft: approval clears them).
3. **Energy-aware execution** — work runs against an energy budget in **Joules**, MODELED for planning, **REAL** measured on NVIDIA hardware (`nvidia-smi`, ∫P·dt).
4. **Hash-chained Reality Ledger** — every step is SHA-256 tamper-evident, **energy columns inside the chain**.

Money (USD) and energy (Joules) are **two independent hard caps**: both checked *before* approval, and a human `--approve` can lift **neither**.

## Quick start
```bash
python3 runner.py --no-real-stripe --approve scale-to-500-leads gpu-render-batch --depth 2
open current-dashboard.html        # the full dashboard (governance, energy telemetry, ledger, reality matrix)
```
You'll see two refused actions, both pre-approved and still BLOCKED:
- `scale-to-500-leads` — over the **$300** money cap.
- `gpu-render-batch` — cheap in money (~$5) but over the **50,000 J** energy cap → *money would have allowed it; the physics cap refused it.*

## Verify the claims (boring, judge-friendly)
```bash
python3 eval_skill.py     # dual caps survive --approve, energy is inside the hash chain (tamper-checked),
                          # honest labeling, child inherits the energy budget, physics conservation — all PASS
python3 test_caps.py      # dual-cap regression
```

## REAL vs MODELED (honesty)
This MacBook has no `nvidia-smi`, so its energy is the **deterministic fallback simulator**, labeled
**MODELED** everywhere — never presented as REAL. The **REAL measured Joules** (and the `REAL · nvidia-smi`
pills + the hero telemetry curve) come from running on an **RTX 4070** — see [`4070-CAPTURE.md`](4070-CAPTURE.md).
The Landauer kT·ln2 floor is annotated **THEORETICAL** only; it never drives a cap.

## What's where
- `protos_core.py` — pure governance kernel: dual-cap `evaluate_guardrails`, `EnergyBudget`, `PhysicsEnergyModel`, hash-chained ledger inputs.
- `telemetry.py` — `NvidiaSmiProvider` (REAL) + deterministic `FallbackSimulator` (MODELED) + `EnergyMeter` (∫P·dt).
- `physics_task.py` — pure-stdlib velocity-Verlet solver with conservation checks (the real work that's metered).
- `runner.py` — orchestration, the hash-chained audit ledger, the dashboard, the installable bundle.
- `eval_skill.py` / `test_caps.py` — verification.
- `bundle/` — the installable Hermes skill + `physics-model.yaml` (energy contract) + `TELEMETRY.md` + `install.sh`.
- `video/` — `make_frames.py` + `build_video.py` (8-beat demo pipeline) + `video-script.md`.
- `submission-artifacts/` — tracked sample run (the live `out/` is gitignored); `real-run-4070/` lands after the capture.
- `CLAUDE_CONTEXT.md` / `ARCHITECTURE_GOALS.md` — full product spec + design targets.

Built by evolving the Protos governance kernel into a physics-first design. Every figure is tagged
real, modeled, theoretical, or dry-run — nothing is presented as more real than it is.
