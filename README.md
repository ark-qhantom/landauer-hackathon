# Landauer

**Physics-Grounded Agent Treasury Framework** for the Hermes Agent Accelerated Business Hackathon (Nous Research × NVIDIA × Stripe).

## Quick Start
```bash
cd /Users/qhantom/landauer-hackathon
python3 runner.py --approve quality-review-leads allocate-revenue scale-to-500-leads --depth 2
# View current-dashboard.html (extend for energy graphs)
```

## Core Idea
General framework for Hermes agents where budgets are dual (money + real energy from NVIDIA hardware physics). Unbreakable caps survive human approval. Tamper-evident ledger with entropy notes. Real Stripe earn/spend under physics constraints. Same code scales from solo laptop to enterprise DGX.

See CLAUDE_CONTEXT.md for full spec (for AI collaborators) and ARCHITECTURE_GOALS.md for design targets.

Original reference logic pulled from /Users/qhantom/protos/hackathon/ per PULL_POLICY.md in reference/.

## Submission Focus
- 1-3 min video with live telemetry, blocked physics action, real Stripe, full Reality Ledger.
- Working demo with measurable energy accounting.
- Clean, ambitious, general-use (not vertical-specific).

Built by evolving Protos strengths into physics-first design under tight 5-day timeline.

## Project Structure
- Core: protos_core.py (evolve governance), runner.py (telemetry + demo)
- Reference: reference/ (ORIGIN.md, PULL_POLICY.md)
- Artifacts: Extend original bundle/skills/dashboard for physics.
- Context for collaborators: CLAUDE_CONTEXT.md + ARCHITECTURE_GOALS.md

Run with real NVIDIA hardware for telemetry (nvidia-smi). Fallback simulator available.

## Next
See CLAUDE_CONTEXT.md for detailed instructions. This is a clean project for the "Landauer" evolution.