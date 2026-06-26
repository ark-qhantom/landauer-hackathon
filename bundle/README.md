# revenue-ops-lead-to-revenue — Hermes workflow bundle

A deployable, governed lead-to-revenue workflow for Hermes, produced by a Landauer cycle.
Contents:
- `skills/revenue-ops-lead-to-revenue/SKILL.md` — the compounded v2 Hermes skill (frontmatter + physics-aware workflow)
- `runs/<run>.yaml` — the governed run definition (money + energy budgets, guardrails, per-action physics) the engine executes
- `physics-model.yaml` — the dual-cap energy contract (budget, power envelope, telemetry) the skill runs under
- `TELEMETRY.md` — how REAL nvidia-smi energy measurement works (and the honest MODELED fallback)
- `install.sh` — copies the skill into your Hermes skills dir

## Install
    ./install.sh                       # installs into ~/.hermes/skills
    hermes skills list | grep revenue-ops
    # then invoke the workflow as /revenue-ops inside Hermes

## Run the governed cycle (research -> qualify -> outreach -> bill, with budget hard-stops)
    python3 ../runner.py --run runs/<run>.yaml --approve quality-review-leads allocate-revenue

The governance + physics claims are independently verifiable — run `python3 eval_skill.py` for a boring,
judge-friendly PASS/FAIL check (dual caps survive --approve, energy is inside the hash chain, conservation
holds, labels are honest). The bundle is the unit an operator or enterprise installs to run the workflow.
