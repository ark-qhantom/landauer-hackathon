# revenue-ops-lead-to-revenue — Hermes workflow bundle

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
