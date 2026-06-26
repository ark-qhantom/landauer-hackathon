# Telemetry — REAL energy measurement (and the honest fallback)

Landauer treats energy as a first-class resource: every cycle's energy cost is **measured**, not assumed.

## REAL (NVIDIA hardware)
On a box with `nvidia-smi`, the engine samples `power.draw,temperature.gpu,utilization.gpu` and integrates
power over time — `energy (J) = ∫ P dt` (trapezoidal) — for the actual measured Joules. These are tagged
**REAL · nvidia-smi** in the dashboard and the audit ledger.

    nvidia-smi --query-gpu=power.draw,temperature.gpu,utilization.gpu --format=csv,noheader,nounits -l 1

## MODELED (no GPU)
With no `nvidia-smi`, a deterministic fallback simulator produces a believable idle->load->cooldown power
curve, seeded by (run_id, action_id) so it is reproducible. It is **always labeled MODELED · fallback** and
is never reported as REAL — the REAL telemetry beat hinges on running on the NVIDIA box.

## The cap vs the measurement
The energy CAP gates on a **MODELED projection** (planning, deterministic, in the hash chain). The
**REAL measured** Joules are reconciled afterward and shown alongside. Calibrate `power_envelope` in
`physics-model.yaml` from a real `nvidia-smi` idle + sustained-load reading on your target GPU.
