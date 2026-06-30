"""landauer.adapters.nvidia — real NVIDIA GPU telemetry adapter.

Wraps the validated telemetry layer (telemetry.NvidiaSmiProvider + EnergyMeter). It MEASURES the real
joules of a workload — ∫P·dt integrated over live nvidia-smi samples — and PROJECTS joules for a
not-yet-run job (E ≈ avg_power_W × runtime_s). The decision engine consumes these numbers; this adapter
is the only place GPU telemetry I/O happens. It never fabricates a sample: with no GPU it returns the
honestly-labeled fallback source.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from telemetry import EnergyMeter, NvidiaSmiProvider, get_provider  # noqa: E402


def available() -> bool:
    return NvidiaSmiProvider.available()


def device_name() -> str:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return "no-nvidia-gpu"
    try:
        out = subprocess.run([smi, "--query-gpu=name", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return "unknown"


def project_joules(power_w: float, runtime_s: float) -> float:
    """Pre-execution projection of energy for a proposed job: E ≈ P·t (joules)."""
    return round(max(0.0, power_w) * max(0.0, runtime_s), 2)


def measure(workload, *, hz: float = 10.0, run_id: str = "landauer-demo",
            action_id: str = "run_local_model", fallback_duration_s: float = 2.0) -> dict:
    """Run `workload()` inside an EnergyMeter and return REAL telemetry.

    Returns: joules (∫P·dt), avg_w, peak_c, samples, source ('nvidia-smi'=REAL | 'fallback'=MODELED),
    is_real, telemetry_incomplete, runtime_s (wall), device, and the workload's own return value.

    `fallback_duration_s` scopes the deterministic FallbackSimulator window on a no-GPU box so its MODELED
    joules describe the same interval as the workload. `telemetry_incomplete` flags a REAL provider that
    returned too few samples (e.g. nvidia-smi erroring mid-run) so a degraded reading is never shown clean.
    """
    provider = get_provider(prefer_real=True, run_id=run_id, action_id=action_id,
                            intensity=0.5, duration_s=max(0.2, fallback_duration_s),
                            idle_W=4.5, max_W=285.0)   # realistic 4070-class envelope for the MODELED fallback curve
    t0 = time.perf_counter()
    with EnergyMeter(provider, hz=hz) as meter:
        work_result = workload() if callable(workload) else None
    wall = time.perf_counter() - t0
    r = meter.result
    incomplete = (r.source == "nvidia-smi" and len(r.samples) < 2)
    return {
        "joules": r.measured_joules,
        "avg_w": r.power_W_avg,
        "peak_c": r.temp_C_peak,
        "samples": len(r.samples),
        "source": r.source,
        "is_real": r.is_real,
        "telemetry_incomplete": incomplete,
        "runtime_s": round(wall, 2),
        "device": device_name(),
        "workload_result": work_result,
    }
