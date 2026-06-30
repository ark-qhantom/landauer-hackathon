"""landauer.adapters — real-world I/O, kept out of the pure decision kernel.

  nvidia        : real GPU telemetry (∫P·dt) + joule projection — wraps telemetry.py
  stripe_budget : Stripe-backed treasury; real test-mode spend on allowed actions — wraps stripe_earn.py
  gpu_workload  : a real CUDA workload so the joule numbers reflect actual compute
  hermes        : tight, no-skill Hermes call that proposes the next action as JSON
"""

from . import nvidia, stripe_budget, gpu_workload, hermes

__all__ = ["nvidia", "stripe_budget", "gpu_workload", "hermes"]
