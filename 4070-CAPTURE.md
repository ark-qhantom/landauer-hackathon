# RTX 4070 capture runbook (the REAL-telemetry hero session)

Goal of this one sitting on the box: produce the **REAL** artifacts the video and writeup need — `energy_source=="nvidia-smi"`,
dashboard pills flipped to **REAL · nvidia-smi**, a smooth multi-second power curve, hardware-honest cap numbers, and a
preserved `run-*/` tree. Everything else (frames, writeup) is then done offline against these real artifacts.

> The dev Mac has no `nvidia-smi`, so today's artifacts are all labeled-MODELED fallback. Nothing here fakes REAL —
> the REAL pills only appear once `NvidiaSmiProvider` actually returns samples on the 4070.

## 0. Prereqs on the box
```bash
cd /path/to/landauer-hackathon
nvidia-smi --query-gpu=power.draw,temperature.gpu,utilization.gpu --format=csv,noheader,nounits   # must print 3 numbers
python3 --version            # 3.x ; no numpy/scipy needed (pure stdlib)
pip show stripe >/dev/null 2>&1 || pip install stripe
# Stripe test key + Hermes are already configured in ~/.hermes/.env and ~/.local/bin/hermes (verified).
```

## 1. Smoke-test the REAL provider (it has never executed)
```bash
python3 - <<'PY'
from telemetry import NvidiaSmiProvider, get_provider, EnergyMeter
print("available:", NvidiaSmiProvider.available())
p = get_provider(prefer_real=True, run_id="smoke", action_id="cycle", intensity=0.5, duration_s=2.0)
print("provider:", p.name(), "is_real:", p.is_real())          # MUST be nvidia-smi[...] / True
print("one sample:", p.sample())                               # real W/°C/%
with EnergyMeter(p, hz=5) as m: __import__("time").sleep(2)
print("measured:", m.result.measured_joules, "J  avg", m.result.power_W_avg, "W  src", m.result.source)
PY
```
✅ Pass = provider is `nvidia-smi[gpu0]`, `is_real True`, non-zero Joules, `src nvidia-smi`. If it falls back, fix PATH/parse before continuing.

## 2. Capture idle + sustained-max watts (for calibration)
```bash
nvidia-smi --query-gpu=power.draw,temperature.gpu --format=csv -l 1 | tee /tmp/idle.csv   # ~10s idle, Ctrl-C
# (optional) run any GPU load and capture sustained draw -> /tmp/load.csv
```
Note **idle_W** and **sustained_max_W**. These become the honest power envelope.

## 3. Recalibrate the model to the real hardware (3 small edits)
- `telemetry.py` `FallbackSimulator(... idle_W=60.0, max_W=200.0 ...)` → set to the 4070's measured idle / TGP.
- `protos_core.py` `DEFAULT_IDLE_W` / `DEFAULT_MAX_W` (the MODELED-projection envelope) → same values, so projection ≈ measurement.
- `bundle/runs/revenue-ops-seed-001.yaml` `energy_budget.monthly_energy_limit_joules` (50000) and the `gpu-render-batch`
  `physics.est_duration_s` (500) → choose so normal actions stay well under the cap and `gpu-render-batch` clearly exceeds it,
  using the real max_W (energy ≈ max_W × duration). Keep the block decisive but not absurd.
- Re-run `python3 test_caps.py` and `python3 eval_skill.py` → both must stay green after recalibration.

## 4. Tune the metered window for a cinematic curve
- `runner.py` `PHYS_STEPS = 1_500_000` → bump (e.g. ~8–12M) so the Kepler solve runs **several seconds** on the 4070.
- `runner.py` `EnergyMeter(provider, hz=5)` → optionally raise `hz` (e.g. 10) for a denser sparkline.
- Aim for ≥ ~30–60 samples over a 3–6 s window.

## 5. The canonical capture run (+ raw nvidia-smi side-by-side)
```bash
# terminal A — stream raw telemetry for the side-by-side shot:
nvidia-smi --query-gpu=power.draw,temperature.gpu,utilization.gpu --format=csv -l 1 | tee /tmp/raw-nvidia-smi.csv
# terminal B — the hero run (real Stripe test-mode + real Hermes both fire):
python3 runner.py --approve scale-to-500-leads gpu-render-batch --real-hermes --depth 2
```
(`--real-stripe` defaults ON; the key is present, so this creates real test-mode Stripe objects. For rehearsals use `--no-real-stripe`.)

## 6. Verify REAL, then preserve
```bash
RUN=$(ls -dt out/run-* | head -1); echo "$RUN"
python3 - <<PY
import json; e=json.load(open("$RUN/energy-report.json"))
assert e["energy_source"]=="nvidia-smi" and e["is_real"], e["energy_source"]
print("REAL ✓  measured", e["cycles"][0]["measured_energy_joules"], "J  samples", len(e["cycles"][0]["samples"]))
PY
grep -c "REAL · nvidia-smi" current-dashboard.html        # dashboard pills flipped to REAL
grep -o "prod_[A-Za-z0-9]*\|ch_[A-Za-z0-9]*" "$RUN/stripe-earn.json" | head   # verifiable Stripe ids
# Save the whole tree for offline frame rendering + the writeup:
cp -R "$RUN" submission-artifacts/real-run-4070
```
✅ Done when: `energy_source==nvidia-smi`, dashboard shows REAL pills, Stripe ids are real `prod_/price_/pi_/ch_`, and the `run-*/` tree is copied into `submission-artifacts/real-run-4070`.

## 7. Hand back
Tell me the captured numbers (idle/max W, cap J, measured J, avg W, peak °C, steps, Stripe ids). I'll: render the video
frames from the REAL run JSON, lock the writeup/tweet Reality-Ledger table to these numbers, and finalize submission-artifacts.
```
```
