# ARCHITECTURE_GOALS.md - Landauer

**Goal:** Evolve the original Protos governance kernel into a clean, physics-first architecture where energy/physics constraints are first-class citizens (not bolted-on). Prioritize best long-term design for a general framework (clarity, testability, non-negotiable physics) over quickest hacks. New clean project, deliberate pulls from original via excerpts.

## High-Level Architecture (Target Design)
- **Core Kernel (Evolve from Original Protos, Refactor for Cleanliness):**
  - Keep/extend: ProtosRun, ProposedAction, Guardrails, evaluate_guardrails (make physics checks peer to financial/sensitivity).
  - EnergyBudget dataclass (parallel to existing Budget: monthly_energy_limit_joules, current_energy_joules).
  - Dual-cap logic: budget_blocked OR energy_blocked → status="blocked". Approval clears soft gates only.
  - Ledger: Augment existing hash chain with energy_J, power_W_avg, temp_C, entropy_note (for irreversible actions), dissipation_J (Landauer approx + measured).
  - Reality Ledger: Extend tagging to all physics numbers (REAL = measured telemetry; MODELED = cost estimates; THEORETICAL = Landauer floor).

- **New Physics Layer (First-Class Design):**
  - PhysicsEnergyModel: 
    - estimate_energy(action_intensity, duration_s) -> float (Joules)
    - integrate_telemetry(samples) -> total_joules (from power over time)
    - calculate_dissipation(irreversible_action) -> float (e.g., base + log2(complexity) for commits/compounding)
  - Telemetry Provider Interface:
    - Abstract: get_current_power() -> dict (power, temp, util)
    - Impl: RealNvidiaSmi (subprocess nvidia-smi), FallbackSimulator (deterministic, seeded by action cost)
    - Integration: Context manager or decorator around actions in runner: pre/post capture, compute delta Joules.
  - Constraints: Thermal limits as hard stops (e.g., if temp > threshold during action, block or throttle).
  - Optimization Signal: In metrics/skill, track energy_efficiency (useful_work / joules). Use for compounding heuristics.

- **Runner & Orchestration (Evolve Skeleton):**
  - Extend cycle execution: Wrap actions with telemetry + energy accounting.
  - Demo Task: Self-contained physics solver (e.g., scipy for ODE with conservation assertions; agent can generate/execute). Report measured energy.
  - Child Spawning: Inherit physics budget regime + improved energy heuristics in skill.

- **Dashboard & Visualization:**
  - Extend current-dashboard.html: Energy panel with power graph (live samples), dual P&L (USD + Joules), per-decision energy columns in ledger table.
  - Pills for energy status (ok/blocked). Sparkline for power draw during run.
  - Keep existing style (indigo/pearl/gold, Reality pills).

- **Skill Emission & Bundle (Preserve Pattern, Enhance):**
  - Emit enhanced SKILL.md with physics-aware instructions (e.g., "Qualify leads considering energy cost of outreach").
  - Bundle includes physics model config, telemetry setup.

- **Guardrails Extension (Make Physics Inevitable):**
  - In evaluate_guardrails: After sensitivity hits, compute projected_energy.
  - If projected_energy > limit: hits.append(energy_limit), status=blocked, note="HARD STOP: physics energy exceeded — refused even if approved".
  - Notes in GuardrailReport: Explicitly call out dual independent caps.

## Anti-Patterns to Avoid
- Physics as secondary/labels only (must drive real blocking and accounting).
- Duplicating original logic instead of evolving (use excerpts for reference).
- Over-scoping demo (focus on one cycle + block + telemetry + Stripe + ledger).
- Ignoring Reality Ledger (tag every physics number).
- Messy legacy from original (new project is clean; reference only via pull policy).

## First-Class Principles
- Physics constraints = non-negotiable as financial ones.
- Real telemetry > estimates (measure on hardware; model for planning).
- General + scalable: Configurable regimes (laptop low-power vs. DGX high-throughput).
- Testable: Energy calcs verifiable against nvidia-smi; caps independently testable.
- Submission-Ready: Architecture must support live video demo with graphs, blocked action proof, full artifacts.

## Evolution Plan (High-Level)
1. High-level architecture proposal (this phase).
2. Refactor core (protos_core.py): Add EnergyBudget, PhysicsEnergyModel, extend guardrails/ledger.
3. Telemetry integration (runner.py): Poller + context for actions.
4. Demo task + physics sim (simple scipy conservation example).
5. Dashboard updates + graphs.
6. Skill enhancement + bundle.
7. Testing: Force blocks, compare energy to real measurements, preserve money behavior.
8. Video prep: Adapt original production for new visuals.

This is the target for "best path" clean design. Propose concrete classes/functions/diffs in responses. Always tie back to preserving original strengths while making physics first-class. 

Reference CLAUDE_CONTEXT.md for full product rules and constraints.