"""The LR-QAOA schedule: a linear ramp of the QAOA angles."""

from __future__ import annotations

import numpy as np


def linear_ramp(p: int, delta: float, decimals: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Angles of LR-QAOA with `p` layers and slope `delta / p`.

    gamma_k = k * delta / p rises and beta_k = (p - k + 1) * delta / p falls, k = 1..p.

    Returns:
        (betas, gammas), each of length p.
    """
    k = np.arange(1, p + 1)
    gammas = k * delta / p
    betas = k[::-1] * delta / p
    if decimals is not None:
        betas, gammas = np.round(betas, decimals), np.round(gammas, decimals)
    return betas, gammas


def default_delta(topology: str, nq: int, fractional_gates: bool = False) -> float:
    """Slope used in the paper for each experiment family (override it in the config)."""
    if topology == "FC":
        if nq <= 17:
            return 0.63
        if nq <= 45:
            return 0.3
        return 0.2
    if topology == "1D":
        return 0.75 if fractional_gates else 1.0
    return 0.75  # native layout
