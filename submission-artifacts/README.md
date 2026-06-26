# Landauer — submission artifacts

Tracked example artifacts so a fresh clone has real output to inspect (the live `out/` dir is gitignored).

## What's here
- `sample-run-mac-fallback/` — a complete run produced on the **Mac dev box**, so its energy is the deterministic
  **MODELED fallback** (`energy_source: "fallback"`), labeled as such throughout. Contents:
  - `audit-ledger.csv` / `audit-ledger.json` — the SHA-256 hash-chained governance ledger, **with physics-energy
    columns inside the chain** (`est_energy_joules`, `cumulative_committed_energy_j`, `energy_rule_fired`,
    `energy_override_attempted`, `dissipation_joules`, `entropy_note`, `reality_tag`). Two refused rows:
    `scale-to-500-leads` (money) and `gpu-render-batch` (energy) — both pre-approved, both BLOCKED.
  - `energy-report.json` — per-cycle metered Joules + raw power samples + the physics-task conservation result.
  - `dashboard.html` — the full dashboard (open in a browser).
  - `compounded-skill.md` — the emitted, installable Hermes skill.
  - `spawned-cofounder.yaml` — the runnable child run (inherits the energy budget).
  - `revenue-ops-seed-001-result.json` — the full engine result.
- `verification-output.txt` — output of `python3 eval_skill.py` (the boring PASS/FAIL verification harness).
- `command-transcript.txt` — the exact commands that produced these.
- `real-run-4070/` — **(added after the 4070 capture)** the same artifacts with `energy_source: "nvidia-smi"`
  and REAL measured Joules. This is the source for the video's REAL-telemetry beats. See `../4070-CAPTURE.md`.

## Reality discipline
Every energy number is tagged: **REAL** = measured `nvidia-smi` telemetry (only in `real-run-4070/`); **MODELED** =
the projected cap input and the offline fallback simulator (everything in `sample-run-mac-fallback/`); **THEORETICAL** =
the Landauer kT·ln2 floor (annotation only, never a cap driver); **SIMULATED** = Stripe when no real test charge is run.
Nothing in `sample-run-mac-fallback/` is presented as REAL hardware telemetry.

## Regenerate
```bash
python3 runner.py --no-real-stripe --approve scale-to-500-leads gpu-render-batch --depth 2   # MODELED rehearsal
python3 eval_skill.py     # verify the governance + physics claims
python3 test_caps.py      # dual-cap regression
```
For the REAL artifacts, run on an NVIDIA box per `../4070-CAPTURE.md`.
