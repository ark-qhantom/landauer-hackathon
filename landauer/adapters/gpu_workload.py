"""landauer.adapters.gpu_workload — a real GPU workload so NVIDIA telemetry is meaningful.

Runs a CUDA matmul loop for a target wall-time so the GPU draws real power (~200-285 W on an RTX 4070
Ti SUPER) and the EnergyMeter integrates real joules. With no torch/CUDA, callers fall back to a real
CPU busy-loop (telemetry stays real, the GPU just stays near idle). This module never fakes a draw.
"""

from __future__ import annotations

import time


def gpu_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def gpu_matmul_load(seconds: float = 12.0, size: int = 8192) -> dict:
    """Saturate the GPU with back-to-back fp32 matmuls for ~`seconds`. Requires CUDA.

    Sized to stay comfortably under a 5,000 J cap on a 4070-class card (~200-285 W × 12 s ≈ 2.4-3.4 kJ).
    """
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available")
    dev = torch.device("cuda")
    a = torch.randn(size, size, device=dev)
    b = torch.randn(size, size, device=dev)
    torch.cuda.synchronize()
    iterations = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        c = a @ b
        a = (c * 1e-4).contiguous()   # keep values bounded; keep the kernel saturated
        iterations += 1
        if iterations % 8 == 0:
            torch.cuda.synchronize()
    torch.cuda.synchronize()
    return {
        "device": torch.cuda.get_device_name(0),
        "matmul_size": size,
        "iterations": iterations,
        "wall_s": round(time.perf_counter() - t0, 2),
        "flop_estimate": iterations * (2 * size ** 3),
    }


def cpu_fallback_load(seconds: float = 12.0) -> dict:
    """Real CPU busy-loop fallback used when CUDA is unavailable (telemetry stays real, GPU near idle)."""
    t0 = time.perf_counter()
    x = 0.0
    iterations = 0
    while time.perf_counter() - t0 < seconds:
        x += (iterations ** 0.5) % 7.0
        iterations += 1
    return {"device": "cpu", "iterations": iterations, "wall_s": round(time.perf_counter() - t0, 2)}
