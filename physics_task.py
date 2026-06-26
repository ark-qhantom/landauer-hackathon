"""
physics_task.py — a real, self-contained physics computation that Landauer RUNS and MEASURES.

This is the honest substance behind "physics-grounded": the agent does genuine physical work (numerically
integrating a conservative dynamical system) whose correctness is verifiable by explicit CONSERVATION laws,
and whose energy COST is measured on hardware by telemetry.EnergyMeter. Useful work (conservation-respecting
integration steps) over Joules spent = a real energy-efficiency number.

Pure standard library (no numpy/scipy — Python 3.14 has neither here). Integrator is velocity-Verlet, which
is SYMPLECTIC: total energy does not drift secularly, it oscillates within a small bounded band ~O(dt^2), so
"energy is conserved" is a true, checkable claim rather than a hope. Two systems:
  - harmonic_oscillator: 1-D spring; conserves total energy.
  - two_body_orbit:      2-D Kepler orbit in a central 1/r potential; conserves energy AND angular momentum.

Honesty note: this is CPU compute. We do not claim it saturates the GPU. The runner measures the REAL power
drawn while this runs (on the RTX 4070 via nvidia-smi); the longer it runs, the more real Joules it costs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict


@dataclass
class SolveResult:
    system: str
    steps: int
    dt: float
    conserved: bool                  # did every checked invariant stay within tol for the whole run?
    energy_drift_rel: float          # |E_final - E_0| / |E_0|  (final-vs-initial energy error)
    energy_band_rel: float           # (E_max - E_min) / |E_0|   (the bounded symplectic oscillation)
    invariants: Dict[str, float]     # extra conserved quantities + their relative drift (e.g. angular momentum)
    useful_work_units: int           # conservation-respecting integration steps completed (the "useful work")
    summary: str


def harmonic_oscillator(steps: int = 500_000, dt: float = 1e-3, omega: float = 2.0,
                        x0: float = 1.0, v0: float = 0.0, tol: float = 1e-2) -> SolveResult:
    """1-D simple harmonic oscillator, unit mass: a = -omega^2 x. Total energy E = ½v² + ½omega²x²."""
    def accel(x: float) -> float:
        return -(omega * omega) * x

    x, v = x0, v0
    a = accel(x)
    e0 = 0.5 * v * v + 0.5 * omega * omega * x * x
    e_min = e_max = e0
    for _ in range(steps):
        x = x + v * dt + 0.5 * a * dt * dt        # velocity-Verlet position update
        a_new = accel(x)
        v = v + 0.5 * (a + a_new) * dt            # ...velocity update with averaged acceleration
        a = a_new
        e = 0.5 * v * v + 0.5 * omega * omega * x * x
        if e < e_min:
            e_min = e
        if e > e_max:
            e_max = e
    ef = 0.5 * v * v + 0.5 * omega * omega * x * x
    drift = abs(ef - e0) / abs(e0)
    band = (e_max - e_min) / abs(e0)
    conserved = band < tol
    return SolveResult(
        system="harmonic_oscillator", steps=steps, dt=dt, conserved=conserved,
        energy_drift_rel=drift, energy_band_rel=band,
        invariants={"E0": e0, "E_final": ef},
        useful_work_units=steps,
        summary=(f"Harmonic oscillator, {steps:,} Verlet steps: energy conserved within "
                 f"{band:.2e} (band) / {drift:.2e} (final) — {'OK' if conserved else 'DRIFT'}."),
    )


def two_body_orbit(steps: int = 500_000, dt: float = 1e-3, gm: float = 1.0,
                   x0: float = 1.0, vy0: float = 0.8, tol: float = 1e-2) -> SolveResult:
    """2-D orbit of a unit mass in a fixed central 1/r potential: a = -GM r / |r|³.
    Conserves total energy E = ½|v|² - GM/|r| AND angular momentum L = x·vy - y·vx (exact for a central force)."""
    def accel(x: float, y: float):
        r2 = x * x + y * y
        r = math.sqrt(r2)
        f = -gm / (r2 * r)            # -GM / r³, times the position vector below
        return f * x, f * y

    x, y = x0, 0.0
    vx, vy = 0.0, vy0
    ax, ay = accel(x, y)

    def energy(x, y, vx, vy):
        return 0.5 * (vx * vx + vy * vy) - gm / math.sqrt(x * x + y * y)

    def angmom(x, y, vx, vy):
        return x * vy - y * vx

    e0 = energy(x, y, vx, vy)
    l0 = angmom(x, y, vx, vy)
    e_min = e_max = e0
    l_min = l_max = l0
    for _ in range(steps):
        x = x + vx * dt + 0.5 * ax * dt * dt
        y = y + vy * dt + 0.5 * ay * dt * dt
        ax_new, ay_new = accel(x, y)
        vx = vx + 0.5 * (ax + ax_new) * dt
        vy = vy + 0.5 * (ay + ay_new) * dt
        ax, ay = ax_new, ay_new
        e = energy(x, y, vx, vy)
        l = angmom(x, y, vx, vy)
        e_min, e_max = min(e_min, e), max(e_max, e)
        l_min, l_max = min(l_min, l), max(l_max, l)
    ef = energy(x, y, vx, vy)
    e_drift = abs(ef - e0) / abs(e0)
    e_band = (e_max - e_min) / abs(e0)
    l_drift = (l_max - l_min) / abs(l0) if l0 != 0 else 0.0
    conserved = e_band < tol and l_drift < tol
    return SolveResult(
        system="two_body_orbit", steps=steps, dt=dt, conserved=conserved,
        energy_drift_rel=e_drift, energy_band_rel=e_band,
        invariants={"E0": e0, "E_final": ef, "L0": l0, "L_drift_rel": l_drift},
        useful_work_units=steps,
        summary=(f"Kepler 2-body, {steps:,} Verlet steps: energy band {e_band:.2e}, "
                 f"angular-momentum drift {l_drift:.2e} — {'OK' if conserved else 'DRIFT'}."),
    )


_SOLVERS = {"harmonic_oscillator": harmonic_oscillator, "two_body_orbit": two_body_orbit}


def run_solver(system: str = "harmonic_oscillator", steps: int = 500_000, dt: float = 1e-3) -> SolveResult:
    """Dispatch to a named conservative-system solver. More steps = more real compute = more measured Joules."""
    if system not in _SOLVERS:
        raise ValueError(f"unknown system {system!r}; choose from {sorted(_SOLVERS)}")
    return _SOLVERS[system](steps=steps, dt=dt)


if __name__ == "__main__":
    ok = True

    def check(label: str, cond: bool):
        global ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    print("physics_task.py self-test — conservation is the correctness check\n")
    ho = run_solver("harmonic_oscillator", steps=200_000, dt=1e-3)
    print("  " + ho.summary)
    check("harmonic oscillator conserves energy (bounded band < 1e-2)", ho.conserved)
    check("energy band is genuinely small (symplectic)", ho.energy_band_rel < 1e-3)

    kp = run_solver("two_body_orbit", steps=200_000, dt=1e-3)
    print("  " + kp.summary)
    check("Kepler orbit conserves energy AND angular momentum", kp.conserved)
    check("angular momentum drift ~ machine precision", kp.invariants["L_drift_rel"] < 1e-6)

    try:
        run_solver("nope")
        check("unknown system raises ValueError", False)
    except ValueError:
        check("unknown system raises ValueError", True)

    print("\n" + ("ALL PASS ✓" if ok else "SOME FAILED ✗"))
    raise SystemExit(0 if ok else 1)
