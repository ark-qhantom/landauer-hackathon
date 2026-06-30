"""
telemetry.py — Landauer's physics measurement layer (the source of REAL Joules).

This is Layer 0 of Landauer: it turns hardware power draw into measured energy so the rest of the
system can treat ENERGY as a first-class, non-negotiable resource alongside money. It deliberately
imports NOTHING from protos_core — the governance kernel must stay pure (no I/O); all measurement,
subprocess, and threading lives here, runner-side.

PHYSICS
-------
Energy is the time-integral of power:  E (Joules) = ∫ P(t) dt.
We sample instantaneous power P (watts) over the wall-clock duration of an action and integrate with
the trapezoidal rule over the real sample timestamps. 1 W · 1 s = 1 J, so a GPU drawing 200 W for
2 s dissipates 400 J. This measured number — not a constant or an estimate — is what lands REAL in
the ledger and on the dashboard hero panel.

REALITY DISCIPLINE (the honesty moat)
-------------------------------------
Every EnergySample carries its own `source` tag at the DATA level ("nvidia-smi" = REAL measured, or
"fallback" = deterministic MODELED). The tag travels with the number into the hash-chained ledger, so
a simulated Joule can never be silently relabeled as a measured one.

HARDWARE MAP (this project)
---------------------------
- PRIMARY REAL provider: NVIDIA RTX 4070 via native `nvidia-smi`. Drives the hero live-telemetry video
  segment and the dashboard's REAL measured-Joules panel.
- Dev box: this Mac has no nvidia-smi -> the deterministic FallbackSimulator runs the full demo offline,
  ALWAYS labeled "fallback" (MODELED). It is never presented as REAL.
- Optional later: Jetson Nano for a short edge / general-use ("laptop -> workstation -> DGX") capture.

The FallbackSimulator is DETERMINISTIC (seeded by run_id + action_id): identical samples every run, so
video takes are repeatable AND the SHA-256 ledger hash chain is reproducible across runs.
"""

from __future__ import annotations

import abc
import random
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Iterator, List, Optional


# ============================================================================
# SAMPLE  (the atomic measurement; `source` IS the Reality tag, carried with the data)
# ============================================================================

@dataclass(frozen=True)
class EnergySample:
    ts_ms: int          # timestamp in milliseconds (monotonic for REAL; synthetic schedule for fallback)
    power_W: float      # instantaneous power draw (watts)
    temp_C: float       # GPU temperature (Celsius)
    util_pct: float     # GPU utilization (percent)
    source: str         # "nvidia-smi" (REAL measured) | "fallback" (MODELED) — the Reality tag at data level


@dataclass
class EnergyReading:
    """The integrated result of metering one action."""
    measured_joules: float
    power_W_avg: float
    temp_C_peak: float
    samples: List[EnergySample] = field(default_factory=list)
    source: str = "fallback"

    @property
    def is_real(self) -> bool:
        return self.source == "nvidia-smi"


# ============================================================================
# INTEGRATOR  (energy = ∫ P dt, trapezoidal over real timestamps)
# ============================================================================

def integrate_power(samples: List[EnergySample]) -> float:
    """Joules = trapezoidal integral of power_W over the sample timestamps (ms -> s).

    Pure function, no I/O — unit-testable on a Mac with no GPU. Samples are sorted by ts so the
    integral is well-defined regardless of arrival order. 0 or 1 sample -> 0 J (no interval to integrate).
    """
    if len(samples) < 2:
        return 0.0
    pts = sorted(samples, key=lambda s: s.ts_ms)
    joules = 0.0
    for a, b in zip(pts, pts[1:]):
        dt_s = (b.ts_ms - a.ts_ms) / 1000.0
        if dt_s <= 0:
            continue
        joules += 0.5 * (a.power_W + b.power_W) * dt_s   # trapezoid: avg power over the interval × dt
    return joules


# ============================================================================
# PROVIDER INTERFACE
# ============================================================================

class TelemetryProvider(abc.ABC):
    """A source of power/thermal samples. Real (nvidia-smi) and fallback (simulated) share this shape so
    the rest of Landauer never branches on which one is active — only the `source` tag differs."""

    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    def is_real(self) -> bool: ...

    @abc.abstractmethod
    def source(self) -> str:
        """The Reality tag every sample from this provider carries."""

    @abc.abstractmethod
    def sample(self) -> EnergySample:
        """Return ONE instantaneous sample."""

    @abc.abstractmethod
    def stream(self, hz: float) -> Iterator[EnergySample]:
        """Yield samples. REAL: live, ~hz, indefinitely until the consumer stops. FALLBACK: a finite,
        deterministic sequence for the action, then stop (no wall-clock dependence -> reproducible)."""


# ----------------------------------------------------------------------------
# REAL — NVIDIA RTX 4070 (and any nvidia-smi GPU)
# ----------------------------------------------------------------------------

class NvidiaSmiProvider(TelemetryProvider):
    """The designated REAL provider for the primary path (RTX 4070).

    Reads native `nvidia-smi --query-gpu=power.draw,temperature.gpu,utilization.gpu
    --format=csv,noheader,nounits`. RAISES on absence (e.g. this dev Mac) so get_provider() falls back
    LOUDLY — it never fabricates samples, so a "fallback" reading can never be mislabeled "nvidia-smi".
    """

    QUERY = "power.draw,temperature.gpu,utilization.gpu"

    def __init__(self, gpu_index: int = 0, smi_path: Optional[str] = None):
        self.gpu_index = gpu_index
        self.smi_path = smi_path or shutil.which("nvidia-smi")
        if not self.smi_path:
            raise RuntimeError("nvidia-smi not found on PATH — no real GPU telemetry available here "
                               "(expected on the dev Mac; use the FallbackSimulator).")
        self._t0 = time.monotonic()

    @staticmethod
    def available() -> bool:
        return shutil.which("nvidia-smi") is not None

    def name(self) -> str:
        return f"nvidia-smi[gpu{self.gpu_index}]"

    def is_real(self) -> bool:
        return True

    def source(self) -> str:
        return "nvidia-smi"

    def _query_once(self) -> List[float]:
        proc = subprocess.run(
            [self.smi_path, f"--query-gpu={self.QUERY}", "--format=csv,noheader,nounits",
             "-i", str(self.gpu_index)],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"nvidia-smi failed (rc={proc.returncode}): {proc.stderr.strip()[:200]}")
        line = (proc.stdout or "").strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3 or any(p.upper().startswith("[N/A") or p == "" for p in parts[:3]):
            # Some GPUs/driver states report [N/A] for power.draw — surface honestly, don't fake a number.
            raise RuntimeError(f"nvidia-smi returned unusable telemetry: {line!r}")
        return [float(parts[0]), float(parts[1]), float(parts[2])]

    def sample(self) -> EnergySample:
        power_W, temp_C, util_pct = self._query_once()
        ts_ms = int((time.monotonic() - self._t0) * 1000)
        return EnergySample(ts_ms, power_W, temp_C, util_pct, source="nvidia-smi")

    def stream(self, hz: float) -> Iterator[EnergySample]:
        period = 1.0 / max(hz, 0.1)
        while True:
            yield self.sample()
            time.sleep(period)


# ----------------------------------------------------------------------------
# FALLBACK — deterministic, offline, ALWAYS labeled "fallback" (MODELED)
# ----------------------------------------------------------------------------

class FallbackSimulator(TelemetryProvider):
    """Deterministic, offline power/thermal model for the Mac dev loop and reproducible video takes.

    Seeded by (run_id, action_id) -> identical samples every run, so both the on-camera take and the
    SHA-256 ledger hash chain are byte-reproducible. Models a believable idle -> load -> cooldown curve
    whose load level is driven by est_intensity (so the energy block, when it comes, is a consequence of
    the modeled physics, not a magic number). NO numpy/scipy (Python 3.14, neither installed).

    Honesty: source() is always "fallback". This is MODELED, never REAL — the dashboard labels it as such.
    """

    def __init__(self, run_id: str, action_id: str, intensity: float = 0.5, duration_s: float = 2.0,
                 idle_W: float = 4.5, max_W: float = 285.0, idle_temp_C: float = 28.0):
        self.run_id = run_id
        self.action_id = action_id
        self.intensity = max(0.0, min(1.0, intensity))
        self.duration_s = max(0.2, duration_s)
        self.idle_W = idle_W
        self.max_W = max_W
        self.idle_temp_C = idle_temp_C
        self._rng = random.Random(f"{run_id}:{action_id}")   # deterministic jitter
        self._seq: List[EnergySample] = []                    # lazily built per hz
        self._seq_hz: Optional[float] = None
        self._cursor = 0

    def name(self) -> str:
        return "fallback-simulator"

    def is_real(self) -> bool:
        return False

    def source(self) -> str:
        return "fallback"

    def _build_sequence(self, hz: float) -> List[EnergySample]:
        """Deterministic idle -> ramp-up -> sustained-load -> cooldown curve. ts_ms is a synthetic, evenly
        spaced schedule (1/hz), NOT wall-clock — so the sequence is independent of how long real work took."""
        n = max(2, round(self.duration_s * hz))
        step_ms = int(1000.0 / hz)
        load_W = self.idle_W + self.intensity * (self.max_W - self.idle_W)
        peak_temp = self.idle_temp_C + self.intensity * 42.0      # hotter under load
        rng = random.Random(f"{self.run_id}:{self.action_id}:{hz}")   # deterministic for a given hz
        samples: List[EnergySample] = []
        for i in range(n):
            frac = i / (n - 1)                                    # 0..1 across the action
            # Envelope: quick ramp up over first 20%, sustain, ease down over last 20%.
            if frac < 0.2:
                env = frac / 0.2
            elif frac > 0.8:
                env = (1.0 - frac) / 0.2
            else:
                env = 1.0
            power = self.idle_W + (load_W - self.idle_W) * env + rng.uniform(-2.0, 2.0)
            # Temperature lags power (thermal inertia): rises with cumulative load, slow to fall.
            temp = self.idle_temp_C + (peak_temp - self.idle_temp_C) * min(1.0, frac * 1.3) + rng.uniform(-0.5, 0.5)
            util = (self.intensity * 100.0) * env + rng.uniform(-1.5, 1.5)
            samples.append(EnergySample(
                ts_ms=i * step_ms,
                power_W=round(max(0.0, power), 2),
                temp_C=round(max(0.0, temp), 2),
                util_pct=round(max(0.0, min(100.0, util)), 1),
                source="fallback",
            ))
        return samples

    def _ensure(self, hz: float):
        if self._seq_hz != hz:
            self._seq = self._build_sequence(hz)
            self._seq_hz = hz
            self._cursor = 0

    def sample(self) -> EnergySample:
        self._ensure(self._seq_hz or 5.0)
        s = self._seq[min(self._cursor, len(self._seq) - 1)]
        self._cursor += 1
        return s

    def stream(self, hz: float) -> Iterator[EnergySample]:
        # Finite, deterministic, emitted immediately (no sleeping) -> fast + reproducible.
        self._ensure(hz)
        for s in self._seq:
            yield s


# ============================================================================
# METER  (wraps an action; energy accounting is structurally non-bypassable)
# ============================================================================

class EnergyMeter:
    """Context manager that meters the energy of whatever runs inside its `with` block.

    REAL provider: a background thread samples live at ~hz across the action; __exit__ stops it and
    integrates the real timestamps. FALLBACK provider: the deterministic finite sequence is collected
    (instantly) and integrated over its synthetic schedule, so measured_joules is reproducible no matter
    how long the wrapped work actually took.

    Usage:
        with EnergyMeter(provider, hz=5) as meter:
            do_the_action()
        reading = meter.result      # EnergyReading(measured_joules, power_W_avg, temp_C_peak, samples, source)
    """

    def __init__(self, provider: TelemetryProvider, hz: float = 5.0):
        self.provider = provider
        self.hz = hz
        self.samples: List[EnergySample] = []
        self.result: Optional[EnergyReading] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _collect(self):
        for s in self.provider.stream(self.hz):
            self.samples.append(s)
            if self._stop.is_set():
                break

    def __enter__(self) -> "EnergyMeter":
        self._stop.clear()
        self.samples = []
        self._thread = threading.Thread(target=self._collect, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> bool:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        pts = sorted(self.samples, key=lambda s: s.ts_ms)
        self.result = EnergyReading(
            measured_joules=round(integrate_power(pts), 4),
            power_W_avg=round(sum(s.power_W for s in pts) / len(pts), 2) if pts else 0.0,
            temp_C_peak=round(max((s.temp_C for s in pts), default=0.0), 2),
            samples=pts,
            source=(pts[0].source if pts else self.provider.source()),
        )
        return False   # never swallow exceptions from the wrapped action


# ============================================================================
# FACTORY  (real on the 4070; deterministic fallback everywhere else)
# ============================================================================

_PROVIDER_LOGGED = False

def get_provider(prefer_real: bool, *, run_id: str = "", action_id: str = "",
                 intensity: float = 0.5, duration_s: float = 2.0,
                 idle_W: float = 60.0, max_W: float = 200.0,
                 gpu_index: int = 0, quiet: bool = False) -> TelemetryProvider:
    """Return the real nvidia-smi provider when prefer_real AND a GPU is present (the RTX 4070 path);
    otherwise the deterministic, honestly-labeled FallbackSimulator. Logs the choice once."""
    global _PROVIDER_LOGGED
    provider: TelemetryProvider
    if prefer_real and NvidiaSmiProvider.available():
        try:
            provider = NvidiaSmiProvider(gpu_index=gpu_index)
        except Exception as e:                                  # GPU vanished mid-run / unusable telemetry
            provider = FallbackSimulator(run_id, action_id, intensity, duration_s, idle_W, max_W)
            if not quiet and not _PROVIDER_LOGGED:
                print(f"[telemetry] nvidia-smi present but unusable ({e}); using deterministic fallback (MODELED).")
                _PROVIDER_LOGGED = True
            return provider
    else:
        provider = FallbackSimulator(run_id, action_id, intensity, duration_s, idle_W, max_W)
    if not quiet and not _PROVIDER_LOGGED:
        tag = "REAL nvidia-smi" if provider.is_real() else "deterministic FallbackSimulator (MODELED)"
        print(f"[telemetry] provider: {provider.name()} — {tag}")
        _PROVIDER_LOGGED = True
    return provider


# ============================================================================
# SELF-TEST  (runs on the Mac with no GPU: proves determinism + the energy math)
# ============================================================================

if __name__ == "__main__":
    ok = True

    def check(label: str, cond: bool):
        global ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    print("telemetry.py self-test (no GPU required)\n")

    # (a) Determinism: same (run_id, action_id) -> byte-identical sample sequences across two instances.
    print("(a) FallbackSimulator determinism")
    a = FallbackSimulator("run-x", "act-1", intensity=0.8, duration_s=2.0)
    b = FallbackSimulator("run-x", "act-1", intensity=0.8, duration_s=2.0)
    sa, sb = list(a.stream(5)), list(b.stream(5))
    check(f"two instances, same seed -> identical samples (n={len(sa)})", sa == sb and len(sa) > 0)
    c = FallbackSimulator("run-x", "act-2", intensity=0.8, duration_s=2.0)
    check("different action_id -> different samples", list(c.stream(5)) != sa)
    check("source is always 'fallback' (never mislabeled REAL)", all(s.source == "fallback" for s in sa))
    check("is_real() is False", a.is_real() is False)

    # (b) Energy math: hand-known samples vs hand-computed ∫P dt.
    print("\n(b) Trapezoidal integrator  (E = ∫P dt, 1W·1s = 1J)")
    flat = [EnergySample(0, 100, 40, 80, "fallback"),
            EnergySample(1000, 100, 40, 80, "fallback"),
            EnergySample(2000, 100, 40, 80, "fallback")]   # 100W for 2s = 200 J
    j_flat = integrate_power(flat)
    check(f"100W constant for 2s -> 200 J (got {j_flat})", abs(j_flat - 200.0) < 1e-9)
    ramp = [EnergySample(0, 0, 40, 0, "fallback"),
            EnergySample(1000, 100, 40, 100, "fallback")]  # 0->100W over 1s, trapezoid = 50 J
    j_ramp = integrate_power(ramp)
    check(f"0->100W over 1s -> 50 J (got {j_ramp})", abs(j_ramp - 50.0) < 1e-9)
    check("single sample -> 0 J (no interval)", integrate_power(flat[:1]) == 0.0)

    # (c) Intensity drives the curve (so a future energy block is a model consequence, not a magic number).
    print("\n(c) Intensity -> power/energy monotonicity")
    lo = list(FallbackSimulator("r", "a", intensity=0.1, duration_s=2.0).stream(5))
    hi = list(FallbackSimulator("r", "a", intensity=0.9, duration_s=2.0).stream(5))
    check("higher intensity -> higher peak power", max(s.power_W for s in hi) > max(s.power_W for s in lo))
    check("higher intensity -> more measured Joules", integrate_power(hi) > integrate_power(lo))

    # (d) EnergyMeter + factory on this box (no nvidia-smi -> deterministic fallback).
    print("\n(d) EnergyMeter + get_provider on this dev box")
    check(f"NvidiaSmiProvider.available() reflects PATH (={NvidiaSmiProvider.available()})",
          NvidiaSmiProvider.available() == (shutil.which("nvidia-smi") is not None))
    prov = get_provider(prefer_real=True, run_id="run-x", action_id="act-1",
                        intensity=0.8, duration_s=2.0)
    check("prefer_real on a no-GPU box falls back (not faked REAL)", not prov.is_real())
    with EnergyMeter(prov, hz=5) as meter:
        pass   # the wrapped action; fallback samples are deterministic regardless of its duration
    r = meter.result
    check(f"meter produced energy: {r.measured_joules} J, avg {r.power_W_avg} W, peak {r.temp_C_peak}°C, "
          f"source={r.source}", r.measured_joules > 0 and r.source == "fallback")
    # reproducible meter result across two runs (same seed) -> reproducible hash chain later
    with EnergyMeter(get_provider(prefer_real=True, run_id="run-x", action_id="act-1",
                                  intensity=0.8, duration_s=2.0, quiet=True), hz=5) as m2:
        pass
    check(f"metered Joules reproducible across runs ({r.measured_joules} == {m2.result.measured_joules})",
          abs(r.measured_joules - m2.result.measured_joules) < 1e-9)

    print("\n" + ("ALL PASS ✓" if ok else "SOME FAILED ✗"))
    raise SystemExit(0 if ok else 1)
