# CLAUDE_CONTEXT.md - Landauer Project

**Project Name:** Landauer (Physics-Grounded Agent Treasury Framework)
**Location:** /Users/qhantom/landauer-hackathon/
**Original Reference:** /Users/qhantom/protos/hackathon/ (DO NOT modify the original; pull logic via excerpts only)
**Hackathon:** Hermes Agent Accelerated Business Hackathon (Nous Research × NVIDIA × Stripe)
**Deadline:** EOD 2026-06-30
**Timeline:** Intense work 2026-06-25 to 2026-06-29 (all day + night). 5 days max.
**User Goal:** Win 1st place. General-use framework (not a vertical tool like film animation). Ambitious but executable. "Best path" over easiest. Vibe-coding with Claude Code + user's personal review on every step. User will provide feedback and approve before major commits or next phases.

## Product Summary (Source of Truth - Use Exactly)
Landauer is a **general-purpose, installable Hermes skill + framework** that lets agents run real business operations while their entire economic activity is explicitly constrained and audited by the actual physics of computation and NVIDIA hardware.

- **Treating energy (Joules from real power draw) as a first-class, non-negotiable resource** alongside money.
- **Unbreakable dual hard caps** (financial USD + physical energy in Joules) that survive human `--approve`.
- **Tamper-evident audit ledger** augmented with energy, entropy/irreversibility notes (inspired by Landauer's principle).
- **Reality Ledger discipline** (REAL / PROJECTED / SIMULATED tagging on every number and claim).
- **General use across scales**: Same framework for solo devs (RTX laptop respecting thermal/battery physics), small founders (workstation "micro-company"), and enterprise (DGX Spark clusters with full evidentiary audit for compliance/sustainability).

**Target Users (General, Not Specific):**
- Solo devs: Personal agent farms on laptops, self-funding small services while respecting hardware physics.
- Small company founders: "Army of one" revenue/procurement/ops automation with real earn + spend under physics constraints.
- Enterprise: Scalable, auditable agent operations with physics + financial governance (e.g., energy reporting + money trails).

**Core Loop in Demo (What the Video Must Show):**
Agents earn (real Stripe billing for physics-grounded services like energy-efficient simulations or hardware-aware optimizations), spend (via Stripe skills for APIs/SaaS under limits), and run real operations on physical NVIDIA hardware (monitoring power/temp/energy in real-time, executing physics-informed tasks).

**Key Differentiator (Never Done Before Angle):**
While others build specific tools (film agents, procurement, content clippers), Landauer is the **general infrastructure layer** that makes safe, scalable, physically honest agent businesses possible. It grounds the agent economy in real physics (Landauer's principle for irreversible computation + measurable hardware energy) so agents can't "cheat" their budgets or physics limits. This directly addresses the 2026 AI energy crisis and lack of trust when agents touch real money/ops.

**Sponsor Alignment (Max Depth):**
- **Hermes/Nous**: Native skill + framework, self-improving on local models, skill emission, multi-platform.
- **NVIDIA**: Runs on DGX Spark/RTX (persistent local agents). Real telemetry (nvidia-smi/DCGM for power, thermal, energy). Nemotron/Qwen for physics-informed reasoning. NemoClaw for secure sandboxed execution.
- **Stripe**: Real bidirectional earn (billing, payments) + spend/provisioning (Stripe Projects skills) inside physics + financial guardrails with configurable safety limits.

**Submission Deliverables (Must Be Complete):**
- 1-3 minute demo video (tag @NousResearch): Live run on NVIDIA hardware showing the full cycle, real telemetry graphs, Stripe tx (verifiable IDs), blocked high-energy action even after --approve, ledger export, Reality Ledger view. Mix live system + clean cinematic framing. Use existing production pipeline from original (frames, build_video.py style).
- Tweet + long writeup (for Typeform + Discord): One-liner, problem (unbounded agent energy/money risks), solution (physics-grounded framework), Reality Ledger table, run instructions, sponsor callouts.
- Working code + artifacts: Fresh run with real numbers, bundle, skill, dashboard, ledger CSV/JSON with energy columns.
- Everything labeled honestly per Reality Ledger (no overclaims on physics; real = measured telemetry + tx; theoretical = Landauer floor).

**Hard Constraints:**
- 5-day timeline: Focus ruthlessly. Prioritize video (decider for judges) + working demo with real hardware telemetry + blocked physics action + real Stripe + clean Reality Ledger.
- Build on/evolve original Protos strengths (do not full restart from zero). New clean project at this location.
- Physics must be **first-class and non-negotiable**, not bolted-on or labels only. Dual caps independent. Real telemetry drives energy accounting.
- General framework: One installable artifact. Demo illustrates generality via one strong concrete example (physics-efficient sim service) + explicit scale notes.
- Ambitious but executable: Novel hook (physics as currency in agent biz) while leveraging existing code for caps/ledger/Reality/Stripe/skill.
- Vibe-coding style: Iterative, small focused changes. User reviews/approves every major piece before proceeding. No over-engineering.

## Critical Decisions (Do Not Deviate)
- **Project Structure**: Fresh clean repo at /Users/qhantom/landauer-hackathon/. Original Protos at /Users/qhantom/protos/hackathon/ is reference ONLY. Pull logic via pasted excerpts or explicit "base on this from original" instructions. Do not modify original. Use git in new project for clean submission history.
- **Architecture Approach**: Evolve Protos governance/ledger as the kernel. Make physics (EnergyBudget, telemetry, dual caps, entropy) first-class peers. Clean refactor for best design (not easiest). Start with high-level architecture proposal before code.
- **Physics Grounding (Exact Spec)**: 
  - Real hardware: nvidia-smi (or DCGM) for power.draw (W), temp, util → integrated Joules (energy = ∫P dt).
  - Dual caps: Financial + energy (Joules). Both checked BEFORE approval; approval clears sensitivity but NEVER bypasses either.
  - Landauer's + Entropy: Frame irreversible actions (ledger commits, state erasure in compounding, decision finalization) with dissipation costs (theoretical floor + practical measured). Ledger rows include energy_J, power_W, entropy_note, hashes.
  - Agents: Monitor live, optimize scheduling for thermal/power efficiency, run physics-informed tasks (e.g., conservation-obeying sims/optimizations).
  - Demo Task: Simple self-contained physics solver (scipy/numpy for ODE/optimization with explicit conservation checks). Report real energy used.
- **What to Preserve from Original Protos (Elevate, Do Not Reinvent)**:
  - Unbreakable cumulative hard-stop caps (computed before approval, survives --approve).
  - SHA-256 prev_hash + row_hash tamper-evident ledger.
  - Reality Ledger tagging (REAL/PROJECTED/SIMULATED).
  - Stripe earn loop (real test-mode objects, IDs verifiable).
  - Skill emission + bundle/install.sh pattern.
  - Runner orchestration, in-process child spawning/chain, compounding.
  - Guardrails logic (sensitivity hits + budget_blocked independent).
  - Dashboard style and Reality pills.
- **What to Design Fresh**: PhysicsEnergyModel, EnergyBudget dataclass, telemetry integration, dual-cap extension in guardrails, energy/entropy ledger augmentation, power graphs in dashboard, physics-informed demo task, enhanced skill with physics heuristics.
- **Vibe-Coding + Review Process**:
  - Iterative: One focused module/prompt at a time.
  - User reviews EVERYTHING (architecture, code, physics math vs real nvidia-smi output, cap enforcement tests, telemetry accuracy, no breakage of original behavior).
  - Always re-read this file before major responses.
  - Scope: Working demo + video takes priority. Clean, testable code.
  - Honesty: Everything tagged. No hype on physics.
- **Risks to Avoid**: Legacy cruft from original (old runs, creative seeds). Vague physics (use measured telemetry as core value; Landauer as framing). Incomplete video (must show live telemetry + block + Stripe + ledger). Drift from general-use + ambitious novel hook.

## Physics Model (Detailed Spec for Implementation)
- Energy cost: base (from action) + intensity * duration. Calibrate from real nvidia-smi.
- Joules: Integrate power over action time (e.g., average power * seconds).
- Dual cap enforcement: In guardrails, check energy_blocked independently of budget_blocked and approved_ids.
- Irreversible costs: For ledger commits, skill compounding (path merging), add dissipation term (e.g., proportional to log2(complexity) or fixed for commits).
- Telemetry: Lightweight poller (subprocess nvidia-smi --query-gpu=power.draw,temperature.gpu,utilization.gpu --format=csv -l 1). Fallback simulator if no NVIDIA.
- Task: Agent executes or generates code for simple physics solver (e.g., harmonic oscillator or N-body with conservation assertions). Report measured energy.
- Dashboard: Live power/temp/energy graphs (HTML/JS or images from data), dual P&L, per-row energy in ledger table.
- Labels: "REAL: measured from hardware telemetry + tx. MODELED: physics cost estimates. THEORETICAL: Landauer kT ln(2) floor."

## Submission & Demo Rules
- Video (1-3 min, high priority): Use/extend original production (build_video.py, frames, cinematic indigo/pearl/gold). Show command run, Hermes output, real telemetry, Stripe, BLOCKED action (physics reason visible), ledger, skill emit, child spawn. End with "same framework scales from laptop to DGX."
- Writeup/Tweet: Lead with problem (AI energy blowups + untrusted agent money), solution (physics-grounded general framework), Reality table (updated with energy columns), run cmd, links.
- Artifacts: Fresh out/run-*/ with real telemetry data, energy in ledger, real Stripe JSON (status=real, test IDs), working dashboard.
- Test: Force high-energy scenario; confirm block survives approve. Compare energy calc to manual nvidia-smi. Preserve all original behavior for money caps etc.

## Claude Rules (Follow Every Turn)
- Re-read this file (and ARCHITECTURE_GOALS.md) at start of every major response or phase.
- Base new code on pasted excerpts from original Protos when evolving governance/ledger.
- Physics first-class: Never make it secondary or "labels only." Dual caps, real telemetry driving costs.
- Output style: Small, focused, testable changes. Include comments explaining physics. Provide tests or verification steps.
- Scope ruthlessly: Prioritize video-ready demo over perfection. Label everything per Reality Ledger.
- If unclear: Ask for clarification or user review before generating large diffs.
- Final output for user: Always include verification commands (e.g., run telemetry compare, force block test).

This file is the persistent context. Update it as decisions evolve (user will review updates). All previous conversation history is summarized here - do not rely on external memory beyond what's in this file + provided code excerpts. 

## Quick Start Commands for This Project
- Work in /Users/qhantom/landauer-hackathon/
- To reference original: Paste specific function excerpts (e.g., evaluate_guardrails) and say "base the evolution on this excerpt from original at /Users/qhantom/protos/hackathon/protos_core.py"
- Test runs: python3 runner.py --approve ... (extend for physics)
- Video: Use/extend original video/ dir (frames, build_video.py) - adapt for new telemetry graphs.
- Git: Clean history here for submission.

Now, begin with the architecture proposal as specified in the first prompt. Always reference this file.